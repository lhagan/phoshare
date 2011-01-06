#!/usr/bin/env python
"""Reads iPhoto library info, and exports photos and movies."""

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

import getpass
import logging
import os
import re
import sys
import time
import unicodedata

from optparse import OptionParser
from Carbon.File import FSResolveAliasFile
import MacOS

import appledata.iphotodata as iphotodata
import tilutil.exiftool as exiftool
import tilutil.systemutils as su
import tilutil.imageutils as imageutils
import phoshare.phoshare_version
import phoshare.picasaweb as picasaweb

# Maximum diff in file size to be not considered a change (to allow for
# meta data updates for example)
_MAX_FILE_DIFF = 35000

# Fudge factor for file modification times
_MTIME_FUDGE = 3

_logger = logging.getLogger('google')
_logger.setLevel(logging.DEBUG)

# create logger

def region_matches(region1, region2):
    """Tests if two regions (rectangles) match."""
    if len(region1) != len(region2):
        return False
    for i in xrange(len(region1)):
        if abs(region1[i] - region2[i]) > 0.0000001:
            return False
    return True

def delete_album_file(album_file, albumdirectory, msg, options):
    """sanity check - only delete from album directory."""
    if not album_file.startswith(albumdirectory):
        print >> sys.stderr, (
            "Internal error - attempting to delete file "
            "that is not in album directory:\n    %s") % (su.fsenc(album_file))
        return False
    if msg:
        print "%s: %s" % (msg, su.fsenc(album_file))

    if not options.delete:
        if not options.dryrun:
            print "Invoke phoshare with the -d option to delete this file."
        return False
    if options.dryrun:
        return True

    try:
        if os.path.isdir(album_file):
            file_list = os.listdir(album_file)
            for subfile in file_list:
                delete_album_file(os.path.join(album_file, subfile),
                                  albumdirectory, msg, options)
            os.rmdir(album_file)
        else:
            os.remove(album_file)
        return True
    except OSError, ex:
        print >> sys.stderr, "Could not delete %s: %s" % (su.fsenc(album_file),
                                                          ex)
    return False

def resolve_alias(path):
    """Resolves a path to point to the real file if it is a file system alias.
    """
    fs, _, _ = FSResolveAliasFile(path, 1)
    return su.fsdec(fs.as_pathname())
    
class ExportFile(object):
    """Describes an exported image."""

    def __init__(self, photo, export_directory, base_name, options):
        """Creates a new ExportFile object."""
        self.photo = photo
        if options.size:
            extension = "jpg"
        else:
            extension = su.getfileextension(photo.image_path)
        self.export_file = os.path.join(
            export_directory, base_name + '.' + extension)
        # Location of "Original" file, if any.
        originals_folder = u"Originals"
        if options.picasa:
            if (os.path.exists(os.path.join(export_directory,
                                            u".picasaoriginals")) or
                not os.path.exists(os.path.join(export_directory,
                                                u"Originals"))):
                originals_folder = u".picasaoriginals"
        if photo.originalpath:
            self.original_export_file = os.path.join(
                export_directory, originals_folder, base_name + "." +
                su.getfileextension(photo.originalpath))
        else:
            self.original_export_file = None

    def get_photo(self):
        """Gets the associated iPhotoImage."""
        return self.photo

    def _check_need_to_export(self, source_file, options):
        """Returns true if the image file needs to be exported.

        Args:
          source_file: path to image file, with aliases resolved.
          options: processing options.
        """
        if not os.path.exists(self.export_file):
            return True
        if (os.path.getmtime(self.export_file) + _MTIME_FUDGE <
            os.path.getmtime(source_file)):
            su.pout('Changed:  %s: newer version is available: %s vs. %s' %
                    (self.export_file,
                     time.ctime(os.path.getmtime(self.export_file)),
                     time.ctime(os.path.getmtime(source_file))))
            return True
        if not options.size:
            # With creative renaming in iPhoto it is possible to get
            # stale files if titles get swapped between images. Double
            # check the size, allowing for some difference for meta data
            # changes made in the exported copy
            source_size = os.path.getsize(source_file)
            export_size = os.path.getsize(self.export_file)
            diff = abs(source_size - export_size)
            if diff > _MAX_FILE_DIFF or (diff > 32 and options.link):
                su.pout('Changed:  %s: file size: %d vs. %d' %
                        (self.export_file, export_size, source_size))
                return True
        # In link mode, we don't need to check the modification date in the
        # database because we catch the changes by the size check above.
        #if (not options.link and
        #    datetime.datetime.fromtimestamp(os.path.getmtime(
        #       self.export_file)) < self.photo.mod_date):
        #    su.pout('Changed:  %s: modified in iPhoto: %s vs. %s ' % (
        #        self.export_file,
        #        time.ctime(os.path.getmtime(self.export_file)),
        #        self.photo.mod_date))
        #    return True
        return False

    def _generate_original(self, options):
        """Exports the original file."""
        do_original_export = False
        export_dir = os.path.split(self.original_export_file)[0]
        if not os.path.exists(export_dir):
            su.pout("Creating folder " + export_dir)
            if not options.dryrun:
                os.mkdir(export_dir)
        original_source_file = resolve_alias(self.photo.originalpath)
        if os.path.exists(self.original_export_file):
            if (os.path.getmtime(self.original_export_file) + _MTIME_FUDGE <
                os.path.getmtime(original_source_file)):
                su.pout('Changed:  %s: newer version is available: %s vs. %s' %
                        (self.original_export_file,
                         time.ctime(os.path.getmtime(
                             self.original_export_file)),
                         time.ctime(os.path.getmtime(original_source_file))))
                do_original_export = True
            elif not options.size:
                source_size = os.path.getsize(original_source_file)
                export_size = os.path.getsize(self.original_export_file)
                diff = abs(source_size - export_size)
                if diff > _MAX_FILE_DIFF or (diff > 0 and options.link):
                    su.pout('Changed:  %s: file size: %d vs. %d' %
                            (self.original_export_file,
                             export_size, source_size))
                    do_original_export = True
        else:
            do_original_export = True

        do_iptc = (options.iptc == 1 and
                   do_original_export) or options.iptc == 2
        if do_iptc and options.link:
            self.check_iptc_data(original_source_file, options,
                                 is_original=True)
        exists = True  # True if the file exists or was updated.
        if do_original_export:
            exists = imageutils.copy_or_link_file(original_source_file,
                                                  self.original_export_file,
                                                  options.dryrun,
                                                  options.link,
                                                  options.size,
                                                  options.update)
        else:
            _logger.debug(u'%s up to date.', self.original_export_file)
        if exists and do_iptc and not options.link:
            self.check_iptc_data(self.original_export_file, options,
                                 is_original=True)

    def generate(self, options):
        """makes sure all files exist in other album, and generates if
           necessary."""
        source_file = self.photo.image_path
        try:
            do_export = self._check_need_to_export(source_file, options)

            # if we use links, we update the IPTC data in the original file
            do_iptc = (options.iptc == 1 and do_export) or options.iptc == 2
            if do_iptc and options.link:
                if self.check_iptc_data(source_file, options):
                    do_export = True

            exists = True  # True if the file exists or was updated.
            if do_export:
                exists = imageutils.copy_or_link_file(source_file,
                                                      self.export_file,
                                                      options.dryrun,
                                                      options.link,
                                                      options.size,
                                                      options.update)
            else:
                _logger.debug(u'%s up to date.', self.export_file)

            # if we copy, we update the IPTC data in the copied file
            if exists and do_iptc and not options.link:
                self.check_iptc_data(self.export_file, options)

            if (options.originals and self.photo.originalpath and
                not self.photo.rotation_is_only_edit):
                self._generate_original(options)
        except (OSError, MacOS.Error) as ose:
            su.perr("Failed to export %s: %s" % (source_file, ose))

    def get_photo_rectangles(self):
        """Gets a list of photo rectangles for the faces in this image."""
        photo_rectangles = self.photo.face_rectangles
        result = []
        for photo_rectangle in photo_rectangles:
            y = max(0.0, 1.0 - photo_rectangle[1] - photo_rectangle[3])
            result.append((photo_rectangle[0],
                           y,
                           photo_rectangle[2],
                           photo_rectangle[3]))
        return result


    def get_export_keywords(self, do_face_keywords):
        """Returns the list of keywords that should be in the exported image."""
        new_keywords = self.photo.keywords[:]
        if do_face_keywords:
            for keyword in self.photo.getfaces():
                if not keyword in new_keywords:
                    new_keywords.append(keyword)
        return new_keywords

    def _check_person_iptc_data(self, export_file,
                                region_rectangles, region_names, do_faces):
        """Tests if the person names or regions in the export file need to be
           updated.

        Returns: (new_rectangles, new_persons), or (None, None)
        """
        if do_faces:
            photo_rectangles = self.get_photo_rectangles()
            photo_faces = self.photo.faces
        else:
            photo_rectangles = []
            photo_faces = []
        combined_region_names = ','.join(region_names)
        combined_photo_faces = ','.join(photo_faces)
        if combined_region_names != combined_photo_faces:
            su.pout('Updating IPTC for %s because of persons (%s instead of %s)'
                    % (export_file, combined_region_names,
                       combined_photo_faces))
            return (photo_rectangles, photo_faces)

        if len(region_rectangles) != len(photo_rectangles):
            su.pout('Updating IPTC for %s because of number of regions '
                    '(%d vs %d)' %
                    (export_file, len(region_rectangles),
                     len(photo_rectangles)))
            return (photo_rectangles, photo_faces)

        for p in xrange(len(region_rectangles)):
            if not region_matches(region_rectangles[p], photo_rectangles[p]):
                su.pout('Updating IPTC for %s because of region for %s '
                        '(%s vs %s)' %
                        (export_file, region_names[p],
                         ','.join(str(c) for c in region_rectangles[p]),
                         ','.join(str(c) for c in photo_rectangles[p])))
                return (photo_rectangles, photo_faces)

        return (None, None)
    
    def check_iptc_data(self, export_file, options, is_original=False):
        """Tests if a file has the proper keywords and caption in the meta
           data."""
        if not su.getfileextension(export_file) in ("jpg", "tif", "tiff",
                                                    "png", "nef", "cr2"):
            return False

        (file_keywords, file_caption, date_time_original, rating, gps,
         region_rectangles, region_names) = exiftool.get_iptc_data(
            export_file)
        if options.aperture:
            # Aperture maintains all these metadata in the preview files, and
            # does not even save all the information into the .xml file. 
            new_caption = None
            new_keywords = None
            new_date = None
            new_rating = -1
            new_gps = None
        else:
            new_caption = imageutils.get_photo_caption(self.photo,
                                                       options.captiontemplate)
            if not su.equalscontent(file_caption, new_caption):
                su.pout('Updating IPTC for %s because it has Caption "%s" '
                        'instead of "%s".' % (export_file, file_caption,
                                              new_caption))
            else:
                new_caption = None

            new_keywords = self.get_export_keywords(options.face_keywords)
            if not imageutils.compare_keywords(new_keywords, file_keywords):
                su.pout("Updating IPTC for %s because of keywords (%s instead "
                        "of %s)" % (export_file, ",".join(file_keywords),
                                 ",".join(new_keywords)))
            else:
                new_keywords = None

            new_date = None
            if self.photo.date and date_time_original != self.photo.date:
                su.pout("Updating IPTC for %s because of date (%s instead of "
                        "%s)" %
                        (export_file, date_time_original, self.photo.date))
                new_date = self.photo.date

            new_rating = -1
            if self.photo.rating != None and rating != self.photo.rating:
                su.pout("Updating IPTC for %s because of rating (%d instead of "
                        "%d)" % (export_file, rating, self.photo.rating))
                new_rating = self.photo.rating

            new_gps = None
            if options.gps and self.photo.gps:
                if (not gps or not self.photo.gps.is_same(gps)):
                    if gps:
                        old_gps = gps
                    else:
                        old_gps = imageutils.GpsLocation()
                    su.pout("Updating IPTC for %s because of GPS %s vs %s" %
                            (export_file, old_gps.to_string(),
                             self.photo.gps.to_string()))
                    new_gps = self.photo.gps

        # Don't export the faces into the original file (could have been
        # cropped).
        do_faces = options.faces and not is_original
        (new_rectangles, new_persons) = self._check_person_iptc_data(
            export_file, region_rectangles, region_names, do_faces)

        if (new_caption != None or new_keywords != None or new_date or
            new_gps or new_rating != -1 or new_rectangles or new_persons):
            if not options.dryrun:
                exiftool.update_iptcdata(export_file, new_caption, new_keywords,
                                         new_date, new_rating, new_gps,
                                         new_rectangles, new_persons)
            return True
        return False

    def is_part_of(self, file_name):
        """Checks if <file> is part of this image."""
        return self.export_file == file_name

_YEAR_PATTERN_INDEX = re.compile(r'([0-9][0-9][0-9][0-9]) (.*)')

class ExportDirectory(object):
    """Tracks an album folder in the export location."""

    def __init__(self, name, iphoto_container, albumdirectory):
        self.name = name
        self.iphoto_container = iphoto_container
        self.albumdirectory = albumdirectory
        self.files = {}

    def add_iphoto_images(self, images, options):
        """Works through an image folder tree, and builds data for exporting."""
        entries = 0
        template = options.nametemplate

        if images is not None:
            entry_digits = len(str(len(images)))
            for image in images:
                if image.ismovie() and not options.movies:
                    continue
                entries += 1
                image_basename = self.make_album_basename(
                    image,
                    entries,
                    str(entries).zfill(entry_digits),
                    template)
                picture_file = ExportFile(image, self.albumdirectory,
                                          image_basename, options)
                self.files[image_basename] = picture_file

        return entries

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

    def load_album(self, options):
        """walks the album directory tree, and scans it for existing files."""
        if not os.path.exists(self.albumdirectory):
            su.pout("Creating folder " + self.albumdirectory)
            if not options.dryrun:
                os.makedirs(self.albumdirectory)
            else:
                return
        file_list = os.listdir(self.albumdirectory)
        if file_list is None:
            return

        for f in file_list:
            # we won't touch some files
            if imageutils.is_ignore(f):
                continue

            album_file = unicodedata.normalize("NFC",
                                               os.path.join(self.albumdirectory,
                                                            f))
            if os.path.isdir(album_file):
                if (options.originals and
                    (f == "Originals" or (options.picasa and
                                          f == ".picasaoriginals"))):
                    self.scan_originals(album_file, options)
                    continue
                else:
                    delete_album_file(album_file, self.albumdirectory,
                                      "Obsolete export directory", options)
                    continue

            base_name = unicodedata.normalize("NFC",
                                              su.getfilebasename(album_file))
            master_file = self.files.get(base_name)

            # everything else must have a master, or will have to go
            if master_file is None or not master_file.is_part_of(album_file):
                delete_album_file(album_file, self.albumdirectory,
                                  "Obsolete exported file", options)

    def scan_originals(self, folder, options):
        """Scan a folder of Original images, and delete obsolete ones."""
        file_list = os.listdir(folder)
        if not file_list:
            return

        for f in file_list:
            # We won't touch some files.
            if imageutils.is_ignore(f):
                continue

            originalfile = unicodedata.normalize("NFC", os.path.join(folder, f))
            if os.path.isdir(originalfile):
                delete_album_file(originalfile, self.albumdirectory,
                                  "Obsolete export Originals directory",
                                  options)
                continue

            base_name = unicodedata.normalize("NFC",
                                              su.getfilebasename(originalfile))
            master_file = self.files.get(base_name)

            # everything else must have a master, or will have to go
            if (not master_file or
                originalfile != master_file.original_export_file or
                master_file.photo.rotation_is_only_edit):
                delete_album_file(originalfile, originalfile,
                                  "Obsolete Original", options)

    def generate_files(self, options):
        """Generates the files in the export location."""
        if not os.path.exists(self.albumdirectory) and not options.dryrun:
            os.makedirs(self.albumdirectory)
        for f in sorted(self.files):
            self.files[f].generate(options)


class IPhotoFace(iphotodata.IPhotoContainer):
    """A photo container based on a face."""

    def __init__(self, face, images):
        data = {}
        data["KeyList"] = []
        iphotodata.IPhotoContainer.__init__(self, data, "Face", False, images)
        self.images = images
        self.name = face


class ExportLibrary(object):
    """The root of the export tree."""

    def __init__(self, albumdirectory):
        self.albumdirectory = albumdirectory
        self.named_folders = {}
        self._abort = False

    def abort(self):
        """Signals that a currently running export should be aborted as soon
        as possible.
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
                proposed = u'%s_(%d)' % (folder, i)
            else:
                proposed = folder
            if self.named_folders.get(proposed) is None:
                return proposed
            i += 1

    def process_albums(self, albums, album_types, folder_prefix, includes,
                       excludes, options, matched=False):
        """Walks trough an iPhoto album tree, and discovers albums
           (directories)."""
        entries = 0

        include_pattern = re.compile(su.unicode_string(includes))
        exclude_pattern = None
        if excludes:
            exclude_pattern = re.compile(su.unicode_string(excludes))

        # first, do the sub-albums
        for sub_album in albums:
            if self._check_abort():
                return
            sub_name = sub_album.name
            if not sub_name:
                print "Found an album with no name: " + sub_album.albumid
                sub_name = "xxx"

            # check the album type
            if sub_album.albumtype == "Folder" or sub_album.albums:
                sub_matched = matched
                if include_pattern.match(sub_name):
                    sub_matched = True
                new_name = folder_prefix
                if sub_album.albumtype == "Folder":
                    new_name += imageutils.make_foldername(sub_name) + "/"
                self.process_albums(sub_album.albums, album_types, new_name,
                                    includes, excludes, options, sub_matched)
                continue
            elif (sub_album.albumtype == "None" or
                  not sub_album.albumtype in album_types):
                # print "Ignoring " + sub_album.name + " of type " + \
                # sub_album.albumtype
                continue

            if not matched and not include_pattern.match(sub_name):
                _logger.debug(u'Skipping "%s" because it does not match pattern.', sub_name)
                continue

            if exclude_pattern and exclude_pattern.match(sub_name):
                _logger.debug(u'Skipping "%s" because it is excluded.', sub_name)
                continue

            _logger.debug(u'Loading "%s".', sub_name)

            folder_hint = None
            if options.folderhints:
                folder_hint = sub_album.getfolderhint()
            prefix = folder_prefix
            if folder_hint is not None:
                prefix = prefix + imageutils.make_foldername(folder_hint) + "/"
            formatted_name = imageutils.format_album_name(
                sub_album, options.foldertemplate)
            sub_name = prefix + imageutils.make_foldername(formatted_name)
            sub_name = self._find_unused_folder(sub_name)

            # first, do the sub-albums
            if self.process_albums(sub_album.albums, album_types, folder_prefix,
                                  includes, excludes, options, matched) > 0:
                entries += 1

            # now the album itself
            picture_directory = ExportDirectory(
                sub_name, sub_album,
                os.path.join(self.albumdirectory, sub_name))
            if picture_directory.add_iphoto_images(sub_album.images,
                                                   options) > 0:
                self.named_folders[sub_name] = picture_directory
                entries += 1

        return entries

    def load_album(self, options):
        """Loads an existing album (export folder)."""
        if not os.path.exists(self.albumdirectory) and not options.dryrun:
            os.makedirs(self.albumdirectory)

        album_directories = {}
        for folder in self.named_folders.values():
            if self._check_abort():
                return
            album_directories[folder.albumdirectory] = True
            folder.load_album(options)

        self.check_directories(self.albumdirectory, "", album_directories,
                               options)

    def check_directories(self, directory, rel_path, album_directories,
                          options):
        """Checks an export directory for obsolete files."""
        if options.ignore:
            exclude_pattern = re.compile(su.fsdec(options.ignore))
            if exclude_pattern.match(os.path.split(directory)[1]):
                return True
        if not os.path.exists(directory):
            return True
        contains_albums = False
        for f in su.os_listdir_unicode(directory):
            if self._check_abort():
                return
            album_file = os.path.join(directory, f)
            if os.path.isdir(album_file):
                if f == "iPod Photo Cache":
                    su.pout("Skipping " + album_file)
                    continue
                rel_path_file = os.path.join(rel_path, f)
                if album_file in album_directories:
                    contains_albums = True
                elif not self.check_directories(album_file, rel_path_file,
                                                album_directories, options):
                    delete_album_file(album_file, directory,
                                      "Obsolete directory", options)
            else:
                # we won't touch some files
                if imageutils.is_ignore(f):
                    continue
                delete_album_file(album_file, directory, "Obsolete",
                                  options)

        return contains_albums

    def generate_files(self, options):
        """Walks through the export tree and sync the files."""
        if not os.path.exists(self.albumdirectory) and not options.dryrun:
            os.makedirs(self.albumdirectory)
        for ndir in sorted(self.named_folders):
            if self._check_abort():
                break
            self.named_folders[ndir].generate_files(options)


def export_iphoto(library, data, excludes, options):
    """Main routine for exporting iPhoto images."""

    print "Scanning iPhoto data for photos to export..."
    if options.events:
        library.process_albums(data.root_album.albums, ["Event"], u'',
                               options.events, excludes, options)

    if options.albums:
        # ignore: Selected Event Album, Special Roll, Special Month
        library.process_albums(data.root_album.albums,
                               ["Regular", "Published"], u'',
                               options.albums, excludes, options)

    if options.smarts:
        library.process_albums(data.root_album.albums, ["Smart"], u'',
                               options.smarts, excludes, options)

    if options.facealbums:
        library.process_albums(data.getfacealbums(), ["Face"],
                               unicode(options.facealbum_prefix),
                               ".", excludes, options)

    print "Scanning existing files in export folder..."
    library.load_album(options)

    print "Exporting photos from iPhoto to export folder..."
    library.generate_files(options)

USAGE = """usage: %prog [options]
Exports images and movies from an iPhoto library into a folder.

Launches as an application if no options are specified.
"""

def get_option_parser():
    """Gets an OptionParser for the Phoshare command line tool options."""
    p = OptionParser(usage=USAGE)
    p.add_option(
        "-a", "--albums",
        help="""Export matching regular albums. The argument
        is a regular expression. Use -a . to export all regular albums.""")
    p.add_option(
        '--captiontemplate', default='{description}',
      help='Template for IPTC image captions. Default: "{description}".')
    p.add_option(
        '--checkalbumsize',
        help='''If set, list any event or album containing more than the
            specified number of images.''')
    p.add_option(
        "-d", "--delete", action="store_true",
        help="Delete obsolete files that are no longer in your iPhoto library.")
    p.add_option(
        "--dryrun", action="store_true",
        help="""Show what would have been done, but don't change or copy any
             files.""")
    p.add_option("-e", "--events",
                 help="""Export matching events. The argument is
                 a regular expression. Use -e . to export all events.""")
    p.add_option("--export",
                 help="""Export images and movies to specified folder.
                      Any files found in this folder that are not part of the
                      export set will be deleted, and files that match will be
                      overwritten if the iPhoto version of the file is
                      different. d""")
    p.add_option("--facealbums", action='store_true',
                 help="Create albums (folders) for faces")
    p.add_option("--facealbum_prefix", default="",
                 help='Prefix for face folders (use with --facealbums)')
    p.add_option("--face_keywords", action="store_true",
                 help="Copy face names into keywords.")
    p.add_option("-f", "--faces", action="store_true",
                 help="Copy faces into metadata.")
    p.add_option("--folderhints", dest="folderhints", action="store_true",
                 help="Scan event and album descriptions for folder hints.")
    p.add_option("--foldertemplate", default="{name}",
                 help="""Template for naming folders. Default: "{name}".""")
    p.add_option("--gps", action="store_true",
                 help="Process GPS location information")
    p.add_option('--ignore',
                 help="""Pattern for folders to ignore in the export folder (use
                      with --delete if you have extra folders folders that you 
                      don't want iphoto_export to delete.""")
    p.add_option("--iphoto",
                 help="""Path to iPhoto library, e.g.
                 "%s/Pictures/iPhoto Library".""",
                 default="~/Pictures/iPhoto Library")
    p.add_option(
        "-k", "--iptc", action="store_const", const=1, dest="iptc",
        help="""Check the IPTC data of all new or updated files. Checks for
        keywords and descriptions. Requires the program "exiftool" (see
        http://www.sno.phy.queensu.ca/~phil/exiftool/).""")
    p.add_option(
        "-K", "--iptcall", action="store_const", const=2, dest="iptc",
        help="""Check the IPTC data of all files. Checks for
        keywords and descriptions. Requires the program "exiftool" (see
        http://www.sno.phy.queensu.ca/~phil/exiftool/).""")
    p.add_option(
      "-l", "--link", action="store_true",
      help="""Use links instead of copying files. Use with care, as changes made
      to the exported files might affect the image that is stored in the iPhoto
      library.""")
    p.add_option(
      "-n", "--nametemplate", default="{title}",
      help="""Template for naming image files. Default: "{title}".""")
    p.add_option("-o", "--originals", action="store_true",
                      help="Export original files into Originals.")
    p.add_option("--picasa", action="store_true",
                      help="Store originals in .picasaoriginals")
    p.add_option('--picasapassword',  
                 help='PicasaWeb password (optional).')
    p.add_option('--picasaweb',  
                 help='Export to PicasaWeb albums of specified user.') 
    p.add_option("--pictures", action="store_false", dest="movies",
                 default=True,
                 help="Export pictures only (no movies).")
    p.add_option(
      "--size", type='int', help="""Resize images so that neither width or
      height exceeds this size. Converts all images to jpeg.""")
    p.add_option(
        "-s", "--smarts",
        help="""Export matching smart albums. The argument
        is a regular expression. Use -s . to export all smart albums.""")
    p.add_option("-u", "--update", action="store_true",
                      help="Update existing files.")
    p.add_option(
        "-x", "--exclude",
        help="""Don't export matching albums or events. The pattern is a
        regular expression.""")
    p.add_option('--verbose', action='store_true', 
                 help='Print verbose messages.')
    p.add_option('--version', action='store_true', 
                 help='Print build version and exit.')
    return p

def check_aperture_mode(options, parser):
    """Checks use of options with Aperture library."""
    if options.folderhints:
        parser.error("--folderhints not supported with Aperture - use "
                     "Folders.")
    if options.face_keywords or options.gps:
        parser.error("Metadata export (--face_keywords, "
                     "--gps) not supported for Aperture. Update "
                     "your previews to let Aperture update the metadata.")
    if options.iptc > 0 and options.link:
        # With Aperture, we cannot modify the preview files, as they get
        # regenerated automatically by Aperture.
        parser.error("Cannot use --iptc and --link together with an "
                     "Aperture library.")

def main():
    """main routine for phoshare."""
    parser = get_option_parser()
    (options, args) = parser.parse_args()
    if len(args) != 0:
        parser.error("Found some unrecognized arguments on the command line.")

    if options.version:
        print '%s %s' % (phoshare.phoshare_version.PHOSHARE_VERSION,
                         phoshare.phoshare_version.PHOSHARE_BUILD)
        return 1

    if options.iptc > 0 and not exiftool.check_exif_tool():
        print >> sys.stderr, ("Exiftool is needed for the --itpc or --iptcall" +
          " options.")
        return 1

    if options.size and options.link:
        parser.error("Cannot use --size and --link together.")

    if not options.iphoto:
        parser.error("Need to specify the iPhoto library with the --iphoto "
                     "option.")

    if options.export or options.picasaweb or options.checkalbumsize:
        if not (options.albums or options.events or options.smarts or
                options.facealbums):
            parser.error("Need to specify at least one event, album, or smart "
                         "album for exporting, using the -e, -a, or -s "
                         "options.")
    else:
        parser.error("No action specified. Use --export to export from your "
                     "iPhoto library.")

    if options.picasaweb:
        if options.picasapassword:
            google_password = options.picasapassword
        else:
            google_password = getpass.getpass('Google password for %s: ' %
                                              options.picasaweb)

    logging_handler = logging.StreamHandler()
    logging_handler.setLevel(logging.DEBUG if options.verbose else logging.INFO)
    _logger.addHandler(logging_handler)

    album_xml_file = iphotodata.get_album_xmlfile(
        su.expand_home_folder(options.iphoto))
    data = iphotodata.get_iphoto_data(album_xml_file)
    if data.aperture:
        if options.originals:
            data.load_aperture_originals()
        check_aperture_mode(options, parser)
 
    options.aperture = data.aperture
    options.foldertemplate = unicode(options.foldertemplate)
    options.nametemplate = unicode(options.nametemplate)
    options.captiontemplate = unicode(options.captiontemplate)

    if options.checkalbumsize:
        data.checkalbumsizes(int(options.checkalbumsize))

    if options.export:
        album = ExportLibrary(su.expand_home_folder(options.export))
        export_iphoto(album, data, options.exclude, options)
    if options.picasaweb:
        albums = picasaweb.PicasaAlbums(options.picasaweb,
                                        google_password)
        export_iphoto(albums, data, options.exclude, options)


if __name__ == "__main__":
    main()
