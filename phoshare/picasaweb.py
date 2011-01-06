"""Synchronize images with PicasaWeb using Gdata API."""

# Copyright 2010 Google Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import datetime
import os
import re
import sys
import time

import atom
import gdata.photos.service
import gdata.media
import gdata.geo

import tilutil.confirmmanager as confirmmanager
import tilutil.systemutils as su
import tilutil.imageutils as imageutils
import tilutil.throttle as throttle

_ALBUM_URL = 'http://picasaweb.google.com/data/feed/api/user/default/albumid'

_MIN_ONLINE_TIMESTAMP = datetime.datetime(1970, 1, 1, 0, 0, 0)

# Maximum diff in file size to be not considered a change (to allow for
# meta data updates for example)
_MAX_FILE_DIFF = 5000

_NOUPLOAD_KEYWORD = 'Noupload'


def delete_online_photo(client, photo, album_name, msg, options):
    """Delete an online photo."""
    if msg:
        print "%s: %s" % (msg, su.fsenc(album_name) + "/" + photo.title.text)

    if not options.delete:
        if not options.dryrun:
            print "Invoke Phoshare with the -d option to delete this image."
        return False
    if options.dryrun:
        return True

    try:
        client.throttle()
        client.gd_client.Delete(photo)
        return True
    except gdata.photos.service.GooglePhotosException, ex:
        print >> sys.stderr, "Could not delete %s: %s" % (
            su.fsenc(photo.title.text), ex)
        return False
    
def get_picasaweb_date(date_time):
    """Converts a date to PicasaWeb format (string). adjusted for 1/1/1970 or
    later (PicasaWeb does not recognize dates before 1/1/1970).
    
    Args:
      date_time: the datetime.datetime to convert
    Return: the date or 1/1/1970, in PicasaWeb format, whichever is late, or
            None if the date is not set.
    """
    if date_time:
        if date_time < _MIN_ONLINE_TIMESTAMP:
            date_time = _MIN_ONLINE_TIMESTAMP
        return str(int(time.mktime(date_time.timetuple()) * 1000))
    return None

def convert_picasaweb_date(text):
    """Converts a PicasaWeb timestamp to datetime."""
    epoch = float(text) / 1000
    return datetime.datetime.fromtimestamp(epoch)

def convert_atom_timestamp_to_epoch(text):
    """Helper function to convert a timestamp string, for instance
    from atom:updated or atom:published, to milliseconds since Unix epoch
    (a.k.a. POSIX time).

    `2007-07-22T00:45:10.000Z' ->
    """
    return str(int(time.mktime(time.strptime(text.split('.')[0],
                                             '%Y-%m-%dT%H:%M:%S')) * 1000))

def set_picasa_photo_pos(picasa_photo, gps):
    """Assigns GPS coordinates to a PicasaWeb photo object."""
    if not picasa_photo.geo:
        picasa_photo.geo = gdata.geo.Where()
    if not picasa_photo.geo.Point:
        picasa_photo.geo.Point = gdata.geo.Point()
    picasa_photo.geo.Point.pos = gdata.geo.Pos(
        text='%.6f %.6f' % (gps.latitude, gps.longitude))
    
def get_content_type(image_path):
    """Returns the appropriate content type for a media file, based on the
    extension.

    Args:
        image_path: path to the media file.

    Returns:
        Content type string, like "image/jpeg".
    """
    extension = su.getfileextension(image_path)
    if extension == "jpg":
        return "image/jpeg"
    if extension == "mov":
        return "video/quicktime"
    if extension == "m4v":
        return "video/mp4"
    if extension == "avi":
        return "video/avi"
    print >> sys.stderr, ('Uploading of media files with extension %s'
                          ' not supported. Defaulting to image/jpeg: %s') % (
        extension, image_path)
    return "image/jpeg"

def check_media_update(client, picasa_photo, photo, export_name, options):
    """Checks if the media of an online photo needs to be updated, and
    performs the update if necessary.

    Args:
        client: PicasaWeb client.
        picasa_photo: handle to the PicasaWeb photo.
        photo: the IPhotoImage photo.
        export_name: name of image (for output messages).
        options: processing options.

    Returns:
        the picasa_photo handle (after the update).
    """
    needs_update = False

    picasa_updated = convert_atom_timestamp_to_epoch(picasa_photo.updated.text)
    if (int(picasa_updated) < int(get_picasaweb_date(photo.mod_date))):
        print "Changed: %s: newer version is available: %s vs %s." % (
            su.fsenc(export_name), convert_picasaweb_date(picasa_updated),
            photo.mod_date)
        needs_update = True
    else:
        file_updated = str(int(os.path.getmtime(photo.image_path) * 1000))
        if int(picasa_updated) < int(file_updated):
            print "Changed: %s: newer file is available: %s vs %s." % (
                su.fsenc(export_name), convert_picasaweb_date(picasa_updated),
                convert_picasaweb_date(file_updated))
            needs_update = True
    # With creative renaming in iPhoto it is possible to get stale 
    # files if titles get swapped between images. Double check the size,
    # allowing for some difference for meta data changes made in the 
    # exported copy
    source_size = os.path.getsize(photo.image_path)
    export_size = int(picasa_photo.size.text)
    diff = abs(source_size - export_size)
    if diff > _MAX_FILE_DIFF:
        print str.format("Changed:  {:s}: file size: {:,d} vs. {:,d}",
            su.fsenc(export_name), export_size, source_size)
        needs_update = True
    elif diff != 0:
        if options.verbose:
            print str.format("Ignored:  {:s}: file size: {:,d} vs. {:,d}",
                export_name, export_size, source_size)

    if not needs_update:
        return picasa_photo
    if not options.update:
        print "Needs update: " + su.fsenc(export_name) + "."
        print "Use the -u option to update this file."
        return picasa_photo
    print("Updating media: " + export_name)
    if options.dryrun:
        return picasa_photo
    client.throttle()
    return client.gd_client.UpdatePhotoBlob(
        picasa_photo, photo.image_path,
        content_type=get_content_type(photo.image_path))

  
class PicasaClient(object):
    """A PicasaWeb client with a throttle for restricting the query rate."""

    def __init__(self, google_user, google_password, query_rate=0.5):
        self.picasa_throttle = throttle.Throttle(query_rate)
        self.gd_client = gdata.photos.service.PhotosService()
        self.gd_client.email = google_user
        self.gd_client.password = google_password
        self.gd_client.source = 'Phoshare-1'
        self.gd_client.ProgrammaticLogin()

    def throttle(self):
        """Throttles access to the PicasaWeb service to ensure that traffic
           stays within the allowable rates. Call before any call that accesses
           the PicasaWeb service.
        """
        self.picasa_throttle.throttle()
        

class PicasaFile(object):
    """Describes an exported image."""

    def __init__(self, photo, album_name, base_name, options):
        """Creates a new PicasaFile object."""
        self.photo = photo
        self.title = base_name
        if options.size:
            extension = "jpg"
        else:
            extension = su.getfileextension(photo.image_path)
        self.export_file = os.path.join(album_name, base_name + '.' + extension)
        self.picasa_photo = None

    def generate(self, client, album_id, options):
        """makes sure all files exist in other album, and generates if
           necessary."""
        if self.picasa_photo:
            self.generate_update(client, options)
        else:
            print 'New file: %s' % (self.export_file)
            self.upload_insert(client, album_id, options)

    def get_export_keywords(self, options):
        """Get the list of keywords for the uploaded file."""
        new_keywords = self.photo.keywords[:]
        if options.face_keywords:
            for keyword in self.photo.getfaces():
                if not keyword in new_keywords:
                    new_keywords.append(keyword)
        return new_keywords
  
    def generate_update(self, client, options):
        """Attempts to update a photo. If the media file needs updating, deletes
        it first, then adds it back in.

        Args:
           client - the PicasaWeb client
           album_id - the id of the album for this photo
        """
        # check albumFile
        self.picasa_photo = check_media_update(client, self.picasa_photo,
                                               self.photo, self.export_file,
                                               options)
        picasa_photo = self.picasa_photo

        # Now check if any of the meta data needs to be updated.
        needs_update = False
        picasa_title = su.unicode_string(picasa_photo.title.text)
        if self.title != picasa_title:
            print ('Updating meta data for %s because it has Caption "%s" '
                'instead of "%s".') % (su.fsenc(self.export_file),
                                       su.fsenc(picasa_title),
                                       su.fsenc(self.title))
            picasa_photo.title.text = self.title
            needs_update = True

        # Combine title and description because PicasaWeb does not show the
        # title anywhere.
        comment = imageutils.get_photo_caption(self.photo,
                                               options.captiontemplate)
        online_summary = su.unicode_string(picasa_photo.summary.text)
        if not su.equalscontent(comment, online_summary):
            print ("Updating meta data for " + su.fsenc(self.export_file) + 
                  ' because it has description "' +
                  su.fsenc(online_summary) +
                  '" instead of "' + su.fsenc(comment) + '".')
            picasa_photo.summary.text = comment.strip()
            needs_update = True
        
        if self.photo.date:
            photo_time = get_picasaweb_date(self.photo.date)
            if photo_time != picasa_photo.timestamp.text:
                print ('Updating meta data for %s because it has timestamp "'
                       '%s" instead of "%s"') % (
                    su.fsenc(self.export_file),
                    picasa_photo.timestamp.datetime(),
                    self.photo.date)
                picasa_photo.timestamp.text = photo_time
                needs_update = True
        
        export_keywords = self.get_export_keywords(options)
        picasa_keywords = []
        if (picasa_photo.media and picasa_photo.media.keywords and
            picasa_photo.media.keywords.text):
            picasa_keywords = su.unicode_string(
                picasa_photo.media.keywords.text).split(', ')
        else:
            picasa_keywords = []
        if not imageutils.compare_keywords(export_keywords, picasa_keywords):
            print ("Updating meta data for " + su.fsenc(self.export_file) + 
                " because of keywords (" +
                su.fsenc(",".join(picasa_keywords)) + ") instead of (" +
                su.fsenc(",".join(export_keywords)) + ").")
            if not picasa_photo.media:
                picasa_photo.media = gdata.media.Group()
            if not picasa_photo.media.keywords:
                picasa_photo.media.keywords = gdata.media.Keywords()
            picasa_photo.media.keywords.text = ', '.join(export_keywords)
            needs_update = True
        
        if options.gps and self.photo.gps:
            if picasa_photo.geo and picasa_photo.geo.Point:
                picasa_location = imageutils.GpsLocation().from_gdata_point(
                    picasa_photo.geo.Point)
            else:
                picasa_location = imageutils.GpsLocation()
            if not picasa_location.is_same(self.photo.gps):
                print ("Updating meta data for " + su.fsenc(self.export_file) + 
                    " because of GPS " + picasa_location.to_string() +
                    " vs " + self.photo.gps.to_string())
                set_picasa_photo_pos(picasa_photo, self.photo.gps)
                needs_update = True
    
        if not needs_update:
            return
    
        if not options.update:
            print "Needs update: " + su.fsenc(self.export_file) + "."
            print "Use the -u option to update this file."
            return
        print("Updating metadata: " + self.export_file)
        if options.dryrun:
            return
        retry = 0
        wait_time = 1.0
        while True:
            try:
                client.throttle()
                picasa_photo = client.gd_client.UpdatePhotoMetadata(
                    picasa_photo)
                return
            except gdata.photos.service.GooglePhotosException, e:
                retry += 1
                if retry == 10:
                    raise e
                if str(e).find("17 REJECTED_USER_LIMIT") == -1:
                    raise e
                wait_time = wait_time * 2
                print("Retrying after " + wait_time + "s because of " + str(e))
                time.sleep(wait_time)


    def upload_insert(self, client, album_id, options):
        """Uploads a new photo by inserting it into an album.
        """
        if options.dryrun:
            return
        album_url = '%s/%s' % (_ALBUM_URL, album_id)
    
        new_photo = gdata.photos.PhotoEntry()
        new_photo.title = atom.Title(text=self.title)
        comment = imageutils.get_photo_caption(self.photo,
                                               options.captiontemplate)
        if comment:
            new_photo.summary = atom.Summary(text=comment,
                                             summary_type='text')
        new_photo.media = gdata.media.Group()
        new_photo.media.keywords = gdata.media.Keywords(
            text=', '.join(self.get_export_keywords(options)))
        if options.gps and self.photo.gps:
            new_photo.geo = gdata.geo.Where()
            new_photo.geo.Point = gdata.geo.Point()
            new_photo.geo.Point.pos = gdata.geo.Pos(text='%.6f %.6f' % (
                self.photo.gps.latitude, 
                self.photo.gps.longitude))
        # TODO(tilmansp): For some reason, this does not seem to work, and
        # all newly inserted images need a second update cycle to fix the
        # timestamp.
        if self.photo.date:
            new_photo.timestamp = gdata.photos.Timestamp(
                text=get_picasaweb_date(self.photo.date))
       
        client.throttle()
        self.picasa_photo = client.gd_client.InsertPhoto(
            album_url, new_photo, self.photo.image_path,
            content_type=get_content_type(self.photo.image_path))
        

class PicasaAlbum(object):
    """Tracks an album folder in the export location."""
    
    def __init__(self, name, iphoto_container):
        self.name = name
        self.iphoto_container = iphoto_container
        self.files = {}  # name -> PicasaFile
        self.online_album = None
        self.image_suffix = re.compile(
            r'\.(jpeg|jpg|mpg|mpeg|mov|png|tif|tiff)$', re.IGNORECASE)
        

    def add_iphoto_images(self, images, options):
        """Works through an image folder tree, and builds data for exporting."""
        entries = 0
        template = options.nametemplate

        if images is not None:
            entry_digits = len(str(len(images)))
            for image in images:
                if image.ismovie() and not options.movies:
                    continue
                if _NOUPLOAD_KEYWORD in image.keywords:
                    continue
                entries += 1
                image_basename = self.make_album_basename(
                    image,
                    entries,
                    str(entries).zfill(entry_digits),
                    template)
                picture_file = PicasaFile(image, self.name,
                                          image_basename, options)
                self.files[image_basename] = picture_file
        return len(self.files)

    def make_album_basename(self, photo, index, padded_index,
                            name_template):
        """creates unique file name."""
        base_name = imageutils.format_photo_name(photo,
                                                 self.iphoto_container.name,
                                                 index,
                                                 padded_index,
                                                 name_template)
        index = 0
        while True:
            album_basename = base_name
            if index > 0:
                album_basename += "_%d" % (index)
            if self.files.get(album_basename) is None:
                return album_basename
            index += 1
        return base_name
    
    def load_album(self, client, online_albums, options):
        """Walks the album directory tree, and scans it for existing files."""

        if options.verbose:
            print 'Reading online album ' + self.name
        comments = self.iphoto_container.getcommentwithouthints().strip()
        timestamp = get_picasaweb_date(self.iphoto_container.date)
        self.online_album = online_albums.get(self.name)
        if not self.online_album:
            print "Creating album: " + su.fsenc(self.name)
            if not options.dryrun: 
                client.throttle()
                self.online_album = client.gd_client.InsertAlbum(
                    title=self.name,
                    summary=comments,
                    access='private',
                    timestamp=timestamp)
                online_albums[self.name] = self.online_album
            return

        # Check the properties of the online album
        changed = False
        online_album_summary_text = su.unicode_string(
            self.online_album.summary.text)
        if online_album_summary_text != comments:
            print 'Updating summary for online album %s (%s vs. %s)' % (
                su.fsenc(self.name),
                su.fsenc(online_album_summary_text),
                su.fsenc(comments))
            self.online_album.summary.text = comments
            changed = True

        if (timestamp and timestamp != self.online_album.timestamp.text):
            print 'Updating timestamp for online album %s (%s/%s)' % (
                su.fsenc(self.name),
                self.online_album.timestamp.datetime(),
                self.iphoto_container.date)
            self.online_album.timestamp.text = timestamp
            changed = True

        if changed and not options.dryrun:
            client.throttle()
            try:
                self.online_album = client.gd_client.Put(
                    self.online_album, 
                    self.online_album.GetEditLink().href,
                    converter=gdata.photos.AlbumEntryFromString)
            except gdata.photos.service.GooglePhotosException, e:
                print 'Failed to update data for online album %s: %s' % (
                    self.name, str(e))

        # Check the pictures in the online album
        try:
            photos = client.gd_client.GetFeed(
                '/data/feed/api/user/%s/albumid/%s?kind=photo' % (
                    'default', self.online_album.gphoto_id.text))
            for photo in photos.entry:
                # we won't touch some files
                if imageutils.is_ignore(photo.title.text):
                    continue

                photo_name = su.unicode_string(photo.title.text)
                base_name = su.getfilebasename(photo_name)
                master_file = self.files.get(base_name)

                # everything else must have a master, or will have to go
                if master_file is None:
                    delete_online_photo(client, photo, self.name,
                                        "Obsolete online photo", options)
                elif master_file.picasa_photo:
                    delete_online_photo(client, photo, self.name,
                                        "Duplicate online photo", options)
                else:
                    master_file.picasa_photo = photo
        except gdata.photos.service.GooglePhotosException, e:
            print 'Failed to load pictures for online album %s: %s' % (
                self.name, str(e))

    def generate_files(self, client, options):
        """Generates the files in the export location."""
        for f in sorted(self.files):
            try:
                self.files[f].generate(client, 
                                       self.online_album.gphoto_id.text,
                                       options)
            except gdata.photos.service.GooglePhotosException, e:
                print >> sys.stderr, 'Failed to upload %s: %s' % (
                    self.files[f].export_file, str(e))

class PicasaAlbums(object):
    """Online Picasa Albums."""

    def __init__(self, google_user, google_password):
        self.named_folders = {}
        self._abort = False
        self.client = PicasaClient(google_user, google_password)
        self.confirm_manager = confirmmanager.ConfirmManager()
        
    def abort(self):
        """Signal that an ongoing export should be aborted as soon as possible.
        """
        self._abort = True

    def _check_abort(self):
        if self._abort:
            print "Export cancelled."
            return True
        return False

    def _find_unused_folder(self, folder):
        """Returns a folder name based on folder that isn't used yet"""
        i = 0
        while True:
            if i > 0:
                proposed = "%s_(%d)" % (folder, i)
            else:
                proposed = folder
            if self.named_folders.get(proposed) is None:
                return proposed
            i += 1
            
    def delete_online_album(self, album, msg, options):
        """Delete an online album."""
        album_name = su.unicode_string(album.title.text)
        if msg:
            print "%s: %s" % (msg, su.fsenc(album_name))

        if not options.delete:
            if not options.dryrun:
                print "Invoke Phoshare with the -d option to delete this album."
            return False
        if options.dryrun:
            return True
         
        if (self.confirm_manager.confirm(album_name, "Delete " + msg + " " +
                                         album_name + "? ", "ny") != 1):
            print >> sys.stderr, 'Not deleted because not confirmed.'
            return False

        try:
            self.client.throttle()
            self.client.gd_client.Delete(album)
            return True
        except gdata.photos.service.GooglePhotosException, e:
            print >> sys.stderr, "Could not delete %s: %s" % (
                su.fsenc(album_name), e)

    def process_albums(self, albums, album_types, folder_prefix, includes,
                       excludes, options, matched=False):
        """Walks trough an iPhoto album tree, and discovers albums
           (directories)."""
        entries = 0

        include_pattern = re.compile(su.fsdec(includes))
        exclude_pattern = None
        if excludes:
            exclude_pattern = re.compile(su.fsdec(excludes))

        # first, do the sub-albums
        for sub_album in albums:
            if self._check_abort():
                return
            sub_name = sub_album.name
            if not sub_name:
                print "Found an album with no name: " + sub_album.albumid
                sub_name = "xxx"

            # check the album type
            if sub_album.albumtype == "Folder":
                sub_matched = matched
                if include_pattern.match(sub_name):
                    sub_matched = True
                self.process_albums(
                    sub_album.albums, album_types,
                    folder_prefix + imageutils.make_foldername(sub_name) + "/",
                    includes, excludes, options, sub_matched)
                continue
            elif (sub_album.albumtype == "None" or
                  not sub_album.albumtype in album_types):
                # print "Ignoring " + sub_album.name + " of type " + \
                # sub_album.albumtype
                continue

            if not matched and not include_pattern.match(sub_name):
                continue

            if exclude_pattern and exclude_pattern.match(sub_name):
                continue

            sub_name = folder_prefix + imageutils.make_foldername(sub_name)
            sub_name = self._find_unused_folder(sub_name)

            # first, do the sub-albums
            if self.process_albums(sub_album.albums, album_types, folder_prefix,
                                  includes, excludes, options, matched) > 0:
                entries += 1

            # now the album itself
            picture_directory = PicasaAlbum(sub_name, sub_album)
            if picture_directory.add_iphoto_images(sub_album.images,
                                                   options) > 0:
                self.named_folders[sub_name] = picture_directory
                entries += 1

        return entries

    def load_album(self, options):
        """Loads an existing album (export folder)."""
        online_albums = {}
        for album in self.client.gd_client.GetUserFeed().entry:
            if online_albums.has_key(album.title.text):
                self.delete_online_album(album, "duplicate album", options)
            else:
                online_albums[su.unicode_string(album.title.text)] = album
        
        album_directories = {}
        for folder_name in sorted(self.named_folders):
            folder = self.named_folders.get(folder_name)
            if self._check_abort():
                return
            album_directories[folder.name] = True
            folder.load_album(self.client, online_albums, options)

        ignore_pattern = None
        if options.ignore:
            ignore_pattern = re.compile(su.fsdec(options.ignore))
        for album_name in online_albums:
            if self._check_abort():
                return
            if album_name in album_directories:
                continue
            if ignore_pattern and ignore_pattern.match(album_name):
                continue
            # We won't touch some albums
            if imageutils.is_ignore(album_name):
                continue
            self.delete_online_album(online_albums[album_name],
                                     "obsolete album", options)

    def generate_files(self, options):
        """Walks through the export tree and sync the files."""
        for ndir in sorted(self.named_folders):
            if self._check_abort():
                break
            self.named_folders[ndir].generate_files(self.client, options)
            


