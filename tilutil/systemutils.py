'''
Created on May 29, 2009

@author: tilman
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

import filecmp
import os
import subprocess
import sys
import unicodedata

_sysenc = sys.getfilesystemencoding()

def execandcombine(command):
    """execute a shell command, and return all output in a single string."""
    data = execandcapture(command)
    return "\n".join(data)


def execandcapture(command):
    """execute a shell command, and return output lines in a sequence."""
    pipe = None
    try:
        pipe = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT).stdout
        data = []
        while True:
            line = pipe.readline()
            if not line:
                break
            line = line.strip()
            line = line.replace("\r", "\n")
            data.append(line)
        return data
    finally:
        if pipe:
            pipe.close()

def equalscontent(string1, string2):
    """Tests if two strings are equal.
    
    None is treated like an empty string. Trailing and leading whitespace is
    ignored."""
    if not string1:
        string1 = ""
    if not string2:
        string2 = ""
    return string1.strip() == string2.strip()

# FileUtil --------------------------------------------------------------------

def os_listdir_unicode(folder):
    """Returns os.listdir with proper Unicode handling, and sorted"""
    # passing a unicode directory name gives back unicode filenames, passing a
    # str directory name gives back str filenames. On MacOS, filenames come back
    # in Unicode Normalization Form D, so force to form C.
    file_list = [ unicodedata.normalize("NFC", nfd) 
                for nfd in os.listdir(unicode(folder)) ]
    file_list.sort()
    return file_list


def fsenc(value):
    '''Helper to encode a string using the system encoding'''
    if not value:
        return ""
    return value.encode(_sysenc, "replace")

def fsdec(value):
    '''Helper to decode a string using the system encoding'''
    if not value:
        return ""
    return value.decode(_sysenc)

def getfilebasename(file_path):
    """returns the name of a file, without the extension. "/a/b/c.txt" -> "c"."""
    return os.path.basename(os.path.splitext(file_path)[0])


def getfileextension(file_path):
    """returns the extension of a file, e.g. '/a/b/c.txt' -> 'txt'."""
    ext = os.path.splitext(file_path)[1]
    if ext.startswith("."):
        ext = ext[1:]
    return ext.lower()


def issamefile(file1, file2):
    """Tests if the two files have the same contents."""
    return filecmp.cmp(file1, file2, False)


def expand_home_folder(path):
    """Checks if path starts with ~ and expands it to the actual
       home folder."""
    if path.startswith("~"):
        return os.environ.get('HOME') + path[1:]
    return path
