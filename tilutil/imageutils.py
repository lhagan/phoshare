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

import re
import sys
import tilutil.systemutils as su
import unicodedata

# ImageMagick "convert" tool. Obsolete - should use _SIPS_TOOL only.
CONVERT_TOOL = "convert"

# Image processing tool
_SIPS_TOOL = "sips"

# TODO: make this list configurable, or better, eliminate the need for it.
_IGNORE_LIST = ("pspbrwse.jbf", "thumbs.db", "desktop.ini",
                "ipod photo cache", "picasa.ini",
                "feed.rss", "view online.url",
                "albumdata.xml", "albumdata2.xml", "pkginfo", "imovie data",
                "dir.data", "iphoto.ipspot", "iphotolock.data", "library.data",
                "library.iphoto", "library6.iphoto", "caches")

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
    result = ""
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
    result = u""
    for c in name:
        if c.isalnum() or c.isspace():
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
    return su.getfileextension(file_name) in ("jpg", "jpeg", "tif", "png")

def is_movie_file(file_name):
    """Tests if the file (name or full path) is a movie file."""
    return su.getfileextension(file_name) in ("mov", "avi", "m4v", "mpg")

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

def resize_image(input, output, height_width_max, format='jpeg',
                 enlarge=False):
    """Converts an image to a new format and resizes it.

    Args:
      input: path to input image file.
      output: path to output image file.
      height_width_max: resize image so height and width aren't greater
          than this value.
      format: output file format (like "jpeg")
      enlarge: if set, enlarge images that are smaller than height_width_max.

    Returns:
        Output from running "sips" command if it failed, None on success.
    """
    # To use ImageMagick:
    #result = su.execandcombine(
    #    [imageutils.CONVERT_TOOL, input, '-delete', '1--1', '-quality', '90%',
    #    '-resize', "%dx%d^" % (height_width_max, height_width_max),output])
    out_height_width_max = 0
    if enlarge:
        out_height_width_max = height_width_max
    else:
        (width, height) = get_image_width_height(input)
        if height > height_width_max or width > height_width_max:
            out_height_width_max = height_width_max
    args = [_SIPS_TOOL, '-s', 'format', format]
    if out_height_width_max:
        args.extend(['--resampleHeightWidthMax', '%d' % (out_height_width_max)])
    args.extend([input, '--out', output])
    result = su.execandcombine(args)
    if result.find('Error:') != -1 or result.find('Warning:') != -1:
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
    if len(new_keywords) != len(old_keywords):
        return False
    new_sorted = sorted([k.strip() for k in new_keywords])
    old_sorted = sorted([k.strip() for k in old_keywords])
    return new_sorted == old_sorted

class GpsLocation(object):
    """Tracks a Gps location (without altitude), as latitude and longitude.
    """
    _MIN_GPS_DIFF = 0.0000005

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
        return (abs(self.latitude - other.latitude) < self._MIN_GPS_DIFF and
                abs(self.longitude - other.longitude) < self._MIN_GPS_DIFF)

    def to_string(self):
        """Returns the location as a string in (37.645267, -11.419373) format.
        """
        return '(%.6f, %.6f)' % (self.latitude, self.longitude)

_CAPTION_PATTERN_INDEX = re.compile(
    r'([0-9][0-9][0-9][0-9])([0-9][0-9])([0-9][0-9]) (.*) - [0-9]+')
_CAPTION_PATTERN = re.compile(
    r'([0-9][0-9][0-9][0-9])([0-9][0-9])([0-9][0-9]) (.*)')

def get_photo_caption(photo, caption_template):
    """Gets the caption for a IPhotoImage photo, using a template. Supports:
       {caption} - the iPhoto caption (title).
       {description} - the iPhoto comment.
       {dated_caption_description} - the caption and comments from an
           IPhotoImage combined into a single string, nicely formatted like
           YYYY/MM/DD title: description.

       Args:
         photo - an IPhotoImage photo.
         caption_template - a format string.
    """
    result = photo.caption
    m = re.match(_CAPTION_PATTERN_INDEX, result)
    if not m:
        m = re.match(_CAPTION_PATTERN, result)
    if m:
        if m.group(2) == '00' and m.group(3) == '00':
            result = '%s %s' % (m.group(1), m.group(4))
        elif m.group(3) == '00':
            result = '%s/%s %s' % (m.group(1), m.group(2), m.group(4))
        else:
            result = '%s/%s/%s %s' % (
                m.group(1), m.group(2), m.group(3), m.group(4))
    if photo.comment:
        result += ': ' + photo.comment

    return caption_template.format(caption=photo.caption,
                                   description=photo.comment,
                                   dated_caption_description=result)

    
