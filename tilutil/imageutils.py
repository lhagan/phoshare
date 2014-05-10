'''Helpers to use with images files

@author: tsporkert@gmail.com
'''

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

import logging
import os
import re
import shutil
import sys
import tilutil.systemutils as su
import unicodedata

# ImageMagick "convert" tool. Obsolete - should use _SIPS_TOOL only.
CONVERT_TOOL = "convert"

# Image processing tool
_SIPS_TOOL = u"sips"

# TODO: make this list configurable, or better, eliminate the need for it.
_IGNORE_LIST = ("pspbrwse.jbf", "thumbs.db", "desktop.ini",
                "ipod photo cache", "picasa.ini",
                "feed.rss", "view online.url",
                "albumdata.xml", "albumdata2.xml", "pkginfo", "imovie data",
                "dir.data", "iphoto.ipspot", "iphotolock.data", "library.data",
                "library.iphoto", "library6.iphoto", "caches")

class _NullHandler(logging.Handler):
    """A logging handler that doesn't emit anything."""
    def emit(self, record):
        pass

_logger = logging.getLogger("google.imageutils")
_logger.addHandler(_NullHandler())

def check_convert():
    """Tests if ImageMagick convert tool is available. Prints error message
       to sys.stderr if there is a problem."""
    found_it = False
    try:
        output = su.execandcombine([CONVERT_TOOL, "-version" ])
        if output.find("ImageMagick") >= 0:
            found_it = True
    except StandardError:
        pass
    
    if not found_it:
        print >> sys.stderr, """Cannot execute "%s".
    
Make sure you have ImageMagick installed. You can download a copy
from http://www.imagemagick.org/script/index.php
""" % (CONVERT_TOOL)
        return False
    return True

def should_create(options):
    """Returns True if a create should be performed, based on options. Does not
       check options.dryrun."""
    if not options.max_create:
        print 'Item not created because create limit has been reached.'
        return False
    if options.max_create != -1:
        options.max_create -= 1
    return True

def should_delete(options):
    """Returns True if a delete should be performed, based on options. Does not
       check options.dryrun."""
    if not options.delete:
        if not options.dryrun:
            print 'Invoke phoshare with the -d option to delete this item.'
        return False
    if not options.max_delete:
        print 'Item not deleted because delete limit has been reached.'
        return False
    if options.max_delete != -1:
        options.max_delete -= 1
    return True

def should_update(options):
    """Returns True if an update should be performed, based on options. Does not
       check options.dryrun."""
    if not options.update:
        if not options.dryrun:
            print 'Invoke phoshare with the -u option to update this item.'
        return False
    if not options.max_update:
        print 'Item not updated because update limit has been reached.'
        return False
    if options.max_update != -1:
        options.max_update -= 1
    return True

def is_ignore(file_name):
    """returns True if the file name is in a list of names to ignore."""
    if file_name.startswith("."):
        if file_name == ".picasaoriginals":
            return False

        return True
    name = file_name.lower()
    return name in _IGNORE_LIST

def make_foldername(name):
    """Returns a valid folder name by replacing problematic characters."""
    result = u''
    for c in name.strip():
        if c.isdigit() or c.isalpha() or c in (',', ' ', '.', '-'):
            result += c
        elif c == ':':
            result += "."
        else:
            result += '_'
    return result

def make_image_filename(name):
    """Returns a valid file name by replacing problematic characters."""
    result = u''
    for c in name:
        if c.isalnum() or c.isspace() or c == '_':
            result += c
        elif c == ":":
            result += '.'
        elif c == "/" or c == '-':
            result += '-'
        else:
            result += ' '
    return unicodedata.normalize("NFC", result)

def is_image_file(file_name):
    """Tests if the file (name or full path) is an image file."""
    return su.getfileextension(file_name) in ("jpg", "jpeg", "tif", "png",
                                              "psd", "nef", "dng", "cr2")

def is_sharable_image_file(file_name):
    """Tests if the file (name or full path) is an image file in a format suitable for sharing."""
    return su.getfileextension(file_name) in ("jpg", "jpeg", "tif", "png")

def is_movie_file(file_name):
    """Tests if the file (name or full path) is a movie file."""
    return su.getfileextension(file_name) in ("mov", "avi", "m4v", "mpg", "3pg")

def is_media_file(file_name):
    """Tests if the file (name or full path) is either an image or a movie file
    """
    return is_image_file(file_name) or is_movie_file(file_name)

def _get_integer(value):
    """Converts a string into an integer.

    Args:
        value: string to convert.

    Returns:
        value converted into an integer, or 0 if conversion is not possible.
    """
    try:
        return int(value)
    except ValueError:
        return 0

def get_image_width_height(file_name):
    """Gets the width and height of an image file.

    Args:
        file_name: path to image file.

    Returns:
        Tuple with image width and height, or (0, 0) if dimensions could not be
        determined.
    """
    result = su.execandcapture([_SIPS_TOOL, '-g', 'pixelWidth',
                                '-g', 'pixelHeight', file_name])
    height = 0
    width = 0
    for line in result:
        if line.startswith('pixelHeight:'):
            height = _get_integer(line[13:])
        elif line.startswith('pixelWidth:'):
            width = _get_integer(line[12:])
    return (width, height)

def resize_image(source, output, height_width_max, out_format='jpeg',
                 enlarge=False):
    """Converts an image to a new format and resizes it.

    Args:
      source: path to inputimage file.
      output: path to output image file.
      height_width_max: resize image so height and width aren't greater
          than this value.
      out_format: output file format (like "jpeg")
      enlarge: if set, enlarge images that are smaller than height_width_max.

    Returns:
        Output from running "sips" command if it failed, None on success.
    """
    # To use ImageMagick:
    #result = su.execandcombine(
    #    [imageutils.CONVERT_TOOL, source, '-delete', '1--1', '-quality', '90%',
    #    '-resize', "%dx%d^" % (height_width_max, height_width_max),output])
    out_height_width_max = 0
    if enlarge:
        out_height_width_max = height_width_max
    else:
        (width, height) = get_image_width_height(source)
        if height > height_width_max or width > height_width_max:
            out_height_width_max = height_width_max
    args = [_SIPS_TOOL, '-s', 'format', out_format]
    if out_height_width_max:
        args.extend(['--resampleHeightWidthMax', '%d' % (out_height_width_max)])
    # TODO(tilmansp): This has problems with non-ASCII output folders.
    args.extend([source, '--out', output])
    result = su.fsdec(su.execandcombine(args))
    if result.find('Error') != -1 or result.find('Warning') != -1 or result.find('Trace') != -1:
        return result
    return None

def compare_keywords(new_keywords, old_keywords):
    """Compares two lists of keywords, and returns True if they are the same.

    Args:
        new_keywords: first list of keywords
        old_keywords: second list of keywords
    Returns:
        True if the two lists contain the same keywords, ignoring trailing
        and leading whitespace, and order.
    """
    if new_keywords == None:
        new_keywords = []
    if old_keywords == None:
        old_keywords = []
    if len(new_keywords) != len(old_keywords):
        return False
    new_sorted = sorted([k.strip() for k in new_keywords])
    old_sorted = sorted([k.strip() for k in old_keywords])
    return new_sorted == old_sorted

class GpsLocation(object):
    """Tracks a Gps location (without altitude), as latitude and longitude.
    """
    # How much rounding "error" do we allow for two GPS coordinates
    # to be considered identical.
    _MIN_GPS_DIFF = 0.0001

    def __init__(self, latitude=0.0, longitude=0.0):
        """Constructs a GpsLocation object."""
        self.latitude = latitude
        self.longitude = longitude
        
    def from_gdata_point(self, point):
        """Sets location from a Point.
        
        Args:
            point: gdata.geo.Point
        Returns:
            this location.
        """
        if point and point.pos and point.pos.text:
            pos = point.pos.text.split(' ')
            self.latitude = float(pos[0])
            self.longitude = float(pos[1])
        else:
            self.latitude = 0.0
            self.longitude = 0.0
        return self
    
    def from_composite(self, latitude, longitude):
        """Sets location from a latitude and longitude in
        "37.642567 N" format.
        
        Args:
            latitude: latitude like "37.645267 N"
            longitude: longitude like "122.419373 W"
        Returns:
             this location.
        """
        lat_split = latitude.split(' ', 1)
        self.latitude = float(lat_split[0])
        if len(lat_split) > 1 and 'S' == lat_split[1]:
            self.latitude = -self.latitude
        long_split = longitude.split(' ', 1)
        self.longitude = float(long_split[0])
        if len(long_split) > 1 and 'W' == long_split[1]:
            self.longitude = -self.longitude
        return self

    def latitude_ref(self):
        """Returns the latitude suffix as either 'N' or 'S'."""
        return 'N' if self.latitude >= 0.0 else 'S'

    def longitude_ref(self):
        """Returns the longitude suffix as either 'E' or 'W'."""
        return 'E' if self.longitude >= 0.0 else 'W'
    
    def is_same(self, other):
        """Tests if two GpsData locations are equal with regards to GPS accuracy
         (6 decimal digits)
         
         Args:
          other: the GpsLocation to compare against.
        Returns: True if the two locatoins are the same.
        """
        return (abs(self.latitude - other.latitude) <= self._MIN_GPS_DIFF and
                abs(self.longitude - other.longitude) <= self._MIN_GPS_DIFF)

    def to_string(self):
        """Returns the location as a string in (37.645267, -11.419373) format.
        """
        return '(%.6f, %.6f)' % (self.latitude, self.longitude)

_CAPTION_PATTERN_INDEX = re.compile(
    r'([0-9][0-9][0-9][0-9])([0-9][0-9])([0-9][0-9]) (.*) - [0-9]+')
_CAPTION_PATTERN = re.compile(
    r'([0-9][0-9][0-9][0-9])([0-9][0-9])([0-9][0-9]) (.*)')

def check_faces_in_caption(photo):
    """Checks if all faces are mentioned in the caption."""
    comment = photo.comment
    if photo.getfaces() and not comment:
        return False
    for face in photo.getfaces():
        parts = face.split(" ")
        # Look for the full name or just the first name.
        if (comment.find(face) == -1 and
            (len(parts) <= 1 or comment.find(parts[0]) == -1)):
            return False
    return True

# Obsolete
def get_faces_left_to_right(photo):
    """Return a list of face names, sorted by appearance in the image from left to right."""
    faces = photo.getfaces()
    names = {}
    for i in xrange(len(faces)):
        x = photo.face_rectangles[i][0]
        while names.has_key(x):
            x += 0.00001
        names[x] = faces[i]
    return [names[x] for x in sorted(names.keys())]

def get_photo_caption(photo, container, caption_template):
    """Gets the caption for a IPhotoImage photo, using a template. Supports:
       {caption} - the iPhoto caption (title).
       {description} - the iPhoto comment.
       {dated_caption_description} - the caption and comments from an
           IPhotoImage combined into a single string, nicely formatted like
           YYYY/MM/DD title: description.
       {folder_description} - the iPhoto comment from the enclosing event, folder, or album

       Args:
         photo - an IPhotoImage photo.
         caption_template - a format string.
    """
    nodate_title_description = photo.caption
    match = re.match(_CAPTION_PATTERN_INDEX, photo.caption)
    if not match:
        match = re.match(_CAPTION_PATTERN, photo.caption)
    else:
        # Strip off trailing index
        nodate_title_description = '%s%s%s %s' % (
            match.group(1), match.group(2), match.group(3), match.group(4))
    if match:
        # Strip of leading date
        nodate_title_description = nodate_title_description[8:].strip()
    title_description = photo.caption
    if photo.comment:
        title_description += ': ' + photo.comment
        nodate_title_description += ': ' + photo.comment
    folder_description = container.getcommentwithouthints().strip()
        
    if photo.date:
        year = str(photo.date.year)
        month = str(photo.date.month).zfill(2)
        day = str(photo.date.day).zfill(2)
    else:
        year = ''
        month = ''
        day = ''

    names = photo.getfaces()
    if names:
        face_list = '(%s)' % (', '.join(names))
    else:
        face_list = ''

    if check_faces_in_caption(photo):
        opt_face_list = ''
    else:
        opt_face_list = '(%s)' % (', '.join(photo.getfaces()))
    
    try:
        return caption_template.format(
            title=photo.caption,
            description=photo.comment,
            title_description=title_description,
            nodate_title_description=nodate_title_description,
            folder_description=folder_description,
            yyyy=year,
            mm=month,
            dd=day,
            face_list=face_list,
            opt_face_list=opt_face_list).strip()
    except KeyError, ex:
        su.pout(u'Unrecognized field in caption template: %s. Use one of: title, description, '
                'title_description, yyyy, mm, dd.' % (str(ex)))
        return caption_template

_YEAR_PATTERN_INDEX = re.compile(r'([0-9][0-9][0-9][0-9]) (.*)')

def format_album_name(album, name, folder_template):
    """Formats a folder name using a template.

       Args:
         album - an IPhotoContainer.
         name - name of the album (typically from album.album_name)
         folder_template - a format string.
    """
    if name is None:
        name = ''
    ascii_name = name.encode('ascii', 'replace')
    plain_name = ascii_name.replace(' ', '')
   
    nodate_name = name
    match = re.match(_YEAR_PATTERN_INDEX, name)
    if match:
        nodate_name = match.group(2)

    if album.date:
        year = str(album.date.year)
        month = str(album.date.month).zfill(2)
        day = str(album.date.day).zfill(2)
    else:
        year = ''
        month = ''
        day = ''

    folderhint = album.getfolderhint()
    if not folderhint:
        folderhint = ''
    
    try:
        return folder_template.format(
            album=name,
            name=name,
            ascii_name=ascii_name,
            plain_name=plain_name,
            nodate_album=nodate_name,
            hint=folderhint,
            yyyy=year,
            mm=month,
            dd=day)
    except KeyError, ex:
        su.pout(u'Unrecognized field in folder template: %s. Use one of: name, ascii_name, '
                'plain_name, hint, yyyy, mm, dd.' % (str(ex)))
        return folder_template

    
def format_photo_name(photo, album_name, index, padded_index,
                      name_template):
    """Formats an image name based on a template."""
    # default image caption filenames have the file extension on them
    # already, so remove it or the export filename will look like
    # "IMG 0087 JPG.jpg"
    orig_basename = re.sub(
        re.compile(r'\.(jpeg|jpg|mpg|mpeg|mov|png|tif|tiff)$',
                   re.IGNORECASE), '', photo.caption)
    if photo.date:
        year = str(photo.date.year)
        month = str(photo.date.month).zfill(2)
        day = str(photo.date.day).zfill(2)
    else:
        year = ''
        month = ''
        day = ''
    nodate_album_name = album_name
    match = re.match(_YEAR_PATTERN_INDEX, nodate_album_name)
    if match:
        nodate_album_name = match.group(2)
    nodate_event_name = photo.event_name
    match = re.match(_YEAR_PATTERN_INDEX, nodate_event_name)
    if match:
        nodate_event_name = match.group(2)

    ascii_title = orig_basename.encode('ascii', 'replace')
    plain_title = ascii_title.replace(' ', '')
    ascii_album_name = album_name.encode('ascii', 'replace')
    plain_album_name = ascii_album_name.replace(' ', '')
    ascii_event = photo.event_name.encode('ascii', 'replace')
    plain_event = ascii_event.replace(' ', '')

    try:
        formatted_name = name_template.format(index=index,
                                              index0=padded_index,
                                              event_index=photo.event_index,
                                              event_index0=photo.event_index0,
                                              album=album_name,
                                              ascii_album=ascii_album_name,
                                              plain_album=plain_album_name,
                                              event=photo.event_name,
                                              ascii_event=ascii_event,
                                              plain_event=plain_event,
                                              nodate_album=nodate_album_name,
                                              nodate_event=nodate_event_name,
                                              title=orig_basename,
                                              caption=orig_basename, # backward compatibility
                                              ascii_title=ascii_title,
                                              plain_title=plain_title,
                                              yyyy=year,
                                              mm=month,
                                              dd=day)
    except KeyError, ex:
        su.pout(u'Unrecognized field in name template: %s. Use one of: index, index0, event_index, '
                'event_index0, album, ascii_album, event, ascii_event, title, ascii_title, '
                'yyyy, mm, or dd.' % (str(ex)))
        formatted_name = name_template
        
    # Take out invalid characters, like '/'
    return make_image_filename(formatted_name)

def copy_or_link_file(source, target, dryrun=False, link=False, size=None,
                      options=None):
    """copies, links, or converts an image file.

    Returns: True if the file exists.
    """
    try:
        if size:
            mode = " (resize)"
        elif link:
            mode = " (link)"
        else:
            mode = " (copy)"
        if os.path.exists(target):
            _logger.info("Needs update: " + target + mode)
            if options and not should_update(options):
                return True
            if not dryrun:
                os.remove(target)
        else:
            _logger.info("New file: " + target + mode)
            if options and not should_create(options):
                return False
        if dryrun:
            return False
        if link:
            _logger.debug(u'os.link(%s, %s)', source, target)
            os.link(source, target)
        elif size:
            result = resize_image(source, target, size)
            if result:
                _logger.error(u'%s: %s' % (source, result))
                return False
        else:
            _logger.debug(u'shutil.copy2(%s, %s)', source, target)
            shutil.copy2(source, target)
        return True
    except (OSError, IOError) as ex:
        _logger.error(u'%s: %s' % (source, str(ex)))
    return False

def get_missing_face_keywords(iptc_data, face_list=None):
    """Checks if keywords need to be added for faces. Returns the keywords that need
       to be added."""
    missing_keywords = []
    if face_list == None:
        face_list = iptc_data.region_names
    for name in face_list:
        # Look for the full name or just the first name.
        if name in iptc_data.keywords:
            continue
        parts = name.split(" ")
        if len(parts) <= 1 or not parts[0] in iptc_data.keywords:
            missing_keywords.append(name)
    return missing_keywords

def get_missing_face_hierarchical_keywords(iptc_data, face_list=None):
    """Checks if keywords need to be added for faces. Returns the keywords that need
       to be added."""
    missing_keywords = []
    if face_list == None:
        face_list = iptc_data.region_names
    for name in face_list:
        # Look for the full name or just the first name.
        if "People|" + name in iptc_data.hierarchical_subject:
            continue
        parts = name.split(" ")
        if len(parts) <= 1 or not "People|" + parts[0] in iptc_data.hierarchical_subject:
            missing_keywords.append("People|" + name)
    return missing_keywords

def get_face_caption_update(iptc_data, old_caption=None, face_list=None):
    """Checks if the caption of an image needs to be updated to mention
       all persons. Returns the new caption if it needs to be changed,
       None otherwise."""
    if old_caption == None:
        old_caption = iptc_data.caption.strip() if iptc_data.caption else u''
    new_caption = old_caption            

    # See if everybody is mentioned
    all_mentioned = True
    if face_list == None:
        face_list = iptc_data.region_names
    for name in face_list:
        parts = name.split(" ")
        # Look for the full name or just the first name.
        if (old_caption.find(name) == -1 and
            (len(parts) <= 1 or old_caption.find(parts[0]) == -1)):
            all_mentioned = False
            break
    if all_mentioned:
        return None

    new_suffix = '(' + ', '.join(face_list) + ')'
    # See if the old caption ends with what looks like a list of names already.
    if old_caption:
        old_caption = _strip_old_names(old_caption, face_list)
    if old_caption:
        new_caption = old_caption + ' ' + new_suffix
    else:
        new_caption = new_suffix
    return new_caption

def _strip_old_names(caption, names):
    """Strips off a "(name1, name2)" comment from the end of a caption if all the words
       are names."""
    if not caption.endswith(')'):
        return caption
    start = caption.rfind('(')
    if start == -1:
        return caption

    # Check that all mentioned names are in the new list (we don't want to remove
    # a comment if it mentions people that are not tagged)
    substring = caption[start + 1:-1]
    old_names = [n.strip() for n in substring.split(",")]

    # Build a list of new names, using both the full name and just the first name.
    new_names = names[:]
    for name in names:
        parts = name.split(" ")
        if len(parts) > 1:
            new_names.append(parts[0])

    all_mentioned = True
    for old_name in old_names:
        if not old_name in new_names:
            all_mentioned = False
            break
    if not all_mentioned:
        return caption
    # Yes, we got names, so lets strip it off.
    new_caption = caption[:start].strip()
    # Do it recursively in case we've added extra (...) sections before
    return _strip_old_names(new_caption, names)

