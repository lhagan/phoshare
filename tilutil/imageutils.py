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

import sys
import systemutils as su

# ImageMagick "convert" tool
CONVERT_TOOL = "convert"

# Image processing tool
_SIPS_TOOL = "sips"

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

def is_image_file(file_name):
    """Tests if the file (name or full path) is an image file."""
    return su.getfileextension(file_name) in ("jpg", "jpeg", "tif", "png")

def is_movie_file(file_name):
    """Tests if the file (name or full path) is a movie file."""
    return su.getfileextension(file_name) in ("mov", "avi", "m4v", "mpg")

def is_media_file(file_name):
    """Tests if the file (name or full path) is either an image or a movie file"""
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
    #result = su.execandcombine([imageutils.CONVERT_TOOL, input,
    #                            '-delete',
    #                            '1--1', '-quality', '90%', '-resize',
    #                           "%dx%d^" % (height_width_max, height_width_max), output])
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
