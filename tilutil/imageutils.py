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
import systemutils as sysutils

# ImageMagick "convert" tool
CONVERT_TOOL = "convert"

def check_convert():
    """Tests if ImageMagick convert tool is available. Prints error message
       to sys.stderr if there is a problem."""
    found_it = False
    try:
        output = sysutils.execandcombine([CONVERT_TOOL, "-version" ])
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
    return sysutils.getfileextension(file_name) in ("jpg", "jpeg", "tif", "png")

def is_movie_file(file_name):
    """Tests if the file (name or full path) is a movie file."""
    return sysutils.getfileextension(file_name) in ("mov", "avi", "m4v", "mpg")

def is_media_file(file_name):
    """Tests if the file (name or full path) is either an image or a movie file"""
    return is_image_file(file_name) or is_movie_file(file_name)

