'''Helpers to use exiftool to read and update image meta data.
Created on May 29, 2009

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

import cPickle
import datetime
import os
import random
import sys
import tempfile
import time

from xml.dom import minidom
from xml import parsers

import tilutil.systemutils as su
import tilutil.imageutils as imageutils

EXIFTOOL = u"exiftool"
_PEOPLE_PREFIX = u"People|"

# The name of the file for storing cached IPTC data in a folder.
CACHE_NAME = u".phoshare"

# Bump up the version number every time incompatible changes are made to the cached data.
# Causes all cached data to expire.
CACHE_VERSION = "phoshare_7"

# 60 day cache
CACHE_MAX_AGE = 60 * 24 * 60 * 60

class _IptcCacheEntry(object):
    """Cached IPTC data for a file."""

    def __init__(self, file_path, iptc_data):
        self.file_path = file_path
        self.iptc_data = iptc_data
        file_stat = os.stat(file_path)
        self.st_ino = file_stat.st_ino
        self.st_mtime = file_stat.st_mtime
        self.st_size = file_stat.st_size
        self.created = time.time()

    def get_iptc_data(self):
        """Gets the cached IptcData object."""
        return self.iptc_data

    def is_expired(self):
        """Tests if the cached IptcData are expired (too old)."""
        now = time.time()
        # Add a 20% jitter to the cache to avoid expiring all entires at the same time.
        if now - self.created > CACHE_MAX_AGE - CACHE_MAX_AGE * 0.2 * random.random():
            su.pout("Cached data for %s too old, ignoring" % (self.file_path))
            return True
        return False
    
    def is_current(self):
        """Tests if the cached IPTC data are still current."""
        if self.is_expired():
            return False
        try:
            file_stat = os.stat(self.file_path)
            if self.st_ino != file_stat.st_ino:
                # su.pout(u"Inode of cached data for %s changed, ignoring" % (self.file_path))
                return False
            if self.st_mtime != file_stat.st_mtime:
                #su.pout(u"Modification time of cached data for %s changed, ignoring" % (
                #    self.file_path))
                return False
            if self.st_size != file_stat.st_size:
                #su.pout(u"Size of cached data for %s changed, ignoring" % (self.file_path))
                return False
            return True
        except OSError:
            return False
        

class _IptcCache(object):
    """Cached IPTC data for files in a folder."""

    def __init__(self, folder):
        self.cache = {}
        self.folder = folder
        self.cache_version = CACHE_VERSION

    def _save(self):
        """Saves the cache data into the .phoshare file in the current folder."""
        save_path = os.path.join(self.folder, CACHE_NAME)
        out = open(save_path, 'w')
        cPickle.dump(self, out)
        out.close()

    def get_iptc_data(self, image_path):
        """Gets IptcData for an image, either from cache, or by running
           exiftool. Returns an empty IptcData object if iptc data could
           not be read from file."""
        iptc_cache_entry = self.cache.get(image_path)
        if iptc_cache_entry and not iptc_cache_entry.is_current():
            iptc_cache_entry = None
        if not iptc_cache_entry:
            su.pout(u"Running exiftool for %s" % (image_path))
            iptc_data = _get_iptc_data_exiftool(image_path)
            iptc_cache_entry = _IptcCacheEntry(image_path, iptc_data)
            self.cache[image_path] = iptc_cache_entry
            self._save()
        return iptc_cache_entry.get_iptc_data()

    def clear_expired(self):
        """Walks through the cache content, and removes any expired entries. Persists any changes.
        """
        has_changes = False
        for (image_file, iptc_data) in self.cache.items():
            if iptc_data.is_expired():
                del self.cache[image_file]
                has_changes = True
        if has_changes:
            self._save()


def _get_iptc_cache(image_file):
    """Gets the _IptcCache for the folder of image_file."""
    folder = os.path.split(image_file)[0]
    if _get_iptc_cache.cache and _get_iptc_cache.cache.folder == folder:
        return _get_iptc_cache.cache
    
    # We have no cached data, or there are for the wrong folder.
    _get_iptc_cache.cache = None
    save_path = os.path.join(folder, CACHE_NAME)
    if os.path.exists(save_path):
        cache_file = None
        try:
            cache_file = open(save_path)
            _get_iptc_cache.cache = cPickle.load(cache_file)
        except Exception, ex:
            su.perr(u"Could not read Phoshare IPTC cache data from %s: %s." % (
                save_path, unicode(ex)))

        if cache_file:
            cache_file.close()

        # Make sure the folder matches.
        if _get_iptc_cache.cache and _get_iptc_cache.cache.folder != folder:
            _get_iptc_cache.cache = None

        try:
            if _get_iptc_cache.cache and _get_iptc_cache.cache.cache_version != CACHE_VERSION:
                _get_iptc_cache.cache = None
        except AttributeError:
            su.perr(u"Found non-cache data in %s, ignoring" % (folder))
            _get_iptc_cache.cache = None

        if _get_iptc_cache.cache:
            _get_iptc_cache.cache.clear_expired()
    if not _get_iptc_cache.cache:
        _get_iptc_cache.cache = _IptcCache(folder)
    return _get_iptc_cache.cache

# Most recently used cache data.
_get_iptc_cache.cache = None

def check_exif_tool(msgstream=sys.stderr):
    """Tests if a compatible version of exiftool is available."""
    try:
        output = su.execandcombine((EXIFTOOL, "-ver"))
        version = float(output)
        if version < 8.61:
            print >> msgstream, "You have version %f of exiftool." % version
            print >> msgstream, """
Please upgrade to version 8.61 or newer of exiftool. You can download a copy
from http://www.sno.phy.queensu.ca/~phil/exiftool/. Phosare wants to use
the new -X option to read IPTC data in XML format."""
            return False
        return True
    except StandardError:
        print >> msgstream, """Cannot execute "%s".

Make sure you have exiftool installed as /usr/bin/exiftool. You can download a
copy from http://www.sno.phy.queensu.ca/~phil/exiftool/.
""" % (EXIFTOOL)
    return False

def _get_xml_nodevalues(xml_data, tag, data):
    """Extracts one or more node values from an XML element, and appends
       it to the data array. Node values can be directly below the element,
       or a list in <rdf:Bag><rfd:li>...</rfd:li>...</rdf:Bag> format.
    """
    for xml_element in xml_data.getElementsByTagName(tag):
        first_child = xml_element.firstChild
        if (first_child and first_child.nodeValue and first_child.nodeValue != "\n"):
            data.append(first_child.nodeValue)
        for xml_bag in xml_element.getElementsByTagName("rdf:Bag"):
            for xml_li in xml_bag.getElementsByTagName("rdf:li"):
                first_child = xml_li.firstChild
                if first_child:
                    data.append(first_child.nodeValue)

class IptcData(object):
    """Container for Image IPTC data."""

    def __init__(self):
        # If image_file is set, then we have real IPTC data.
        self.image_file = None
        self.keywords = []
        self.caption = ""
        self.date_time_original = None
        self.rating = -1
        self.gps = None
        self.region_names = []
        self.region_rectangles = []
        self.image_width = -1
        self.image_height = -1
        self.hierarchical_subject = []
        self.already_applied = ""

    def has_data(self):
        """Tests if there are real IPTC data."""
        return True if self.image_file else False

    def get_people(self):
        """Gets the list of people, merging region_names and the "People|" category
           keywords."""
        people = self.region_names[:]
        try:
            for keyword in self.hierarchical_subject:
                if keyword.startswith(_PEOPLE_PREFIX):
                    name = keyword[len(_PEOPLE_PREFIX):]
                    if not name in people:
                        people.append(name)
        except AttributeError, ex:
            pass # Old cache files don't have hierarchical_subject
        return people

    def get_category_keywords(self, category):
        """Gets all hierarchical keywords in the given category. E.g. if the
           HierarchicalSubject is "A,B|C", get_category_keywords("B") will
           return "C"."""
        pattern = category + "|"
        keywords = []
        try:
            for keyword in self.hierarchical_subject:
                if keyword.startswith(pattern):
                    keywords.append(keyword[len(pattern):])
        except AttributeError:
            # Old cache files don't have hierarchical_subject
            pass
        return keywords


def get_iptc_data(image_file, use_cache=True):
    """Get IPTC data for a file as an IptcData object. Can use cached data from .phoshare files."""
    iptc_data = None
    if use_cache:
        iptc_cache = _get_iptc_cache(image_file)
        iptc_data = iptc_cache.get_iptc_data(image_file)
    else:
        iptc_data = _get_iptc_data_exiftool(image_file)
    if not iptc_data:
        iptc_data = IptcData()
    return iptc_data


def _get_iptc_data_exiftool(image_file):
    """Returns IptcData for an image file using exiftool."""
    args = [EXIFTOOL, "-X", "-m", "-q", "-q", '-c', '%.6f', "-Keywords", "-Caption-Abstract",
            "-ImageDescription", "-DateTimeOriginal", "-Rating", "-GPSLatitude",
            "-Subject", "-GPSLongitude", "-RegionName", "-RegionType",
            "-RegionAreaX", "-RegionAreaY", "-RegionAreaW", "-RegionAreaH",
            "-ImageWidth", "-ImageHeight", "-HierarchicalSubject", "-AlreadyApplied", image_file ]
    output = su.execandcombine(args)
    if not output:
        return None

    iptc_data = None
    try:
        xml_data = minidom.parseString(output)
        for xml_desc in xml_data.getElementsByTagName('rdf:Description'):
            iptc_data = IptcData()
            iptc_data.rating = 0
            iptc_data.image_file = xml_desc.getAttribute("rdf:about")
            
            iptc_data.keywords = []
            _get_xml_nodevalues(xml_desc, 'IPTC:Keywords', iptc_data.keywords)
            _get_xml_nodevalues(xml_desc, 'XMP-lr:HierarchicalSubject',
                                iptc_data.hierarchical_subject)
            # Keywords can also be stored as Subject in the XMP directory
            _get_xml_nodevalues(xml_desc, 'XMP:Subject', iptc_data.keywords)
            for xml_caption in xml_desc.getElementsByTagName('IPTC:Caption-Abstract'):
                if xml_caption.firstChild:
                    iptc_data.caption = xml_caption.firstChild.nodeValue
            if not iptc_data.caption:
                for xml_caption in xml_desc.getElementsByTagName('IFD0:ImageDescription'):
                    if xml_caption.firstChild:
                        iptc_data.caption = xml_caption.firstChild.nodeValue
            _parse_datetime_original(xml_desc, iptc_data, image_file)
            for xml_element in xml_desc.getElementsByTagName('XMP-xmp:Rating'):
                if xml_element.firstChild:
                    iptc_data.rating = int(xml_element.firstChild.nodeValue)
            _parse_gps(xml_desc, iptc_data)
                
            for xml_element in xml_desc.getElementsByTagName('File:ImageWidth'):
                if xml_element.firstChild:
                    iptc_data.image_width = int(xml_element.firstChild.nodeValue)
            for xml_element in xml_desc.getElementsByTagName('File:ImageHeight'):
                if xml_element.firstChild:
                    iptc_data.image_height = int(xml_element.firstChild.nodeValue)
            for xml_element in xml_desc.getElementsByTagName('XMP-crs:AlreadyApplied'):
                if xml_element.firstChild:
                    iptc_data.already_applied = xml_element.firstChild.nodeValue

            #string_rectangles = []
            #_get_xml_nodevalues(xml_desc, 'XMP-MP:RegionRectangle', string_rectangles)
            #for string_rectangle in string_rectangles:
            #    rectangle = []
            #    for c in string_rectangle.split(','):
            #        rectangle.append(float(c))
            #    iptc_data.region_rectangles.append(rectangle)
            #_get_xml_nodevalues(xml_desc, 'XMP-MP:RegionPersonDisplayName', 
            #                    iptc_data.region_names)

            # Handle Region tags
            _parse_regions(xml_desc, iptc_data)
            break

        xml_data.unlink()
      
    except parsers.expat.ExpatError, ex:
        su.perr('Could not parse exiftool output %s: %s' % (output, ex))

    return iptc_data


def _parse_datetime_original(xml_desc, iptc_data, image_file):
    """Parses the DateTimeOriginal data from exiftool output."""
    for xml_element in xml_desc.getElementsByTagName('ExifIFD:DateTimeOriginal'):
        if not xml_element.firstChild:
            continue
        try:
            date_time_original = time.strptime(
                xml_element.firstChild.nodeValue, '%Y:%m:%d %H:%M:%S')
            iptc_data.date_time_original = datetime.datetime(
                date_time_original.tm_year,
                date_time_original.tm_mon,
                date_time_original.tm_mday,
                date_time_original.tm_hour,
                date_time_original.tm_min,
                date_time_original.tm_sec)
        except ValueError, _ve:
            su.perr('Exiftool returned an invalid date %s for %s - ignoring.' % (
                xml_element.firstChild.nodeValue, image_file))


def _parse_gps(xml_desc, iptc_data):
    """Parses the GPS data from exiftool output."""
    gps_latitude = None
    gps_longitude = None
    for xml_element in xml_desc.getElementsByTagName('Composite:GPSLatitude'):
        if xml_element.firstChild:
            gps_latitude = xml_element.firstChild.nodeValue
    for xml_element in xml_desc.getElementsByTagName('Composite:GPSLongitude'):
        if xml_element.firstChild:
            gps_longitude = xml_element.firstChild.nodeValue
    if gps_latitude and gps_longitude:
        iptc_data.gps = imageutils.GpsLocation().from_composite(gps_latitude, 
                                                                gps_longitude)

        
def _parse_regions(xml_desc, iptc_data):
    """Parses XML region type data into IptcData."""
    region_types = []
    _get_xml_nodevalues(xml_desc, 'XMP-mwg-rs:RegionType', region_types)
    if not region_types:
        return
    region_names = []
    region_area_x = []
    region_area_y = []
    region_area_w = []
    region_area_h = []
    _get_xml_nodevalues(xml_desc, 'XMP-mwg-rs:RegionName', region_names)
    _get_xml_nodevalues(xml_desc, 'XMP-mwg-rs:RegionAreaX', region_area_x)
    _get_xml_nodevalues(xml_desc, 'XMP-mwg-rs:RegionAreaY', region_area_y)
    _get_xml_nodevalues(xml_desc, 'XMP-mwg-rs:RegionAreaW', region_area_w)
    _get_xml_nodevalues(xml_desc, 'XMP-mwg-rs:RegionAreaH', region_area_h)
    # Sort the names as they appear in the image, from left to right
    names = {}
    rectangles = {}
    for i in xrange(min(len(region_area_x), len(region_names))):
        x = float(region_area_x[i])
        rectangle = [x, float(region_area_y[i]), float(region_area_w[i]), float(region_area_h[i])]
        while names.has_key(x):
            x += 0.0000001
        names[x] = region_names[i]
        rectangles[x] = rectangle
    if names:
        iptc_data.region_names = [names[x] for x in sorted(names.keys())]
        iptc_data.region_rectangles = [rectangles[x] for x in sorted(rectangles.keys())]



def update_iptcdata(filepath, new_caption, new_keywords, new_datetime,
                    new_rating, new_gps, new_rectangles, new_persons,
                    image_width=-1, image_height=-1, hierarchical_subject=None,
                    preserve_time=True):
    """Updates the caption and keywords of an image file."""
    # Some cameras write into Description, so we wipe it out to not cause
    # conflicts with Caption-Abstract.
    command = [EXIFTOOL, '-F', '-m', '-Description=']
    if preserve_time:
        command.append("-P")
    tmp = _write_caption_file(new_caption, command)
    if new_datetime:
        try:
            command.append('-DateTimeOriginal="%s"' % (
                new_datetime.strftime("%Y:%m:%d %H:%M:%S")))
        except ValueError, ex:
            su.perr("Cannot update timestamp for %s: %s" % (filepath, str(ex)))
    if new_keywords:
        for keyword in new_keywords:
            command.append(u'-keywords=%s' % (keyword))
    elif new_keywords != None:
        command.append('-keywords=')
    if hierarchical_subject:
        for keyword in hierarchical_subject:
            command.append(u'-HierarchicalSubject=%s' % (keyword))
    elif hierarchical_subject != None:
        command.append('-HierarchicalSubject=')
        command.append('-Subject=')
    if new_rating >= 0:
        command.append('-Rating=%d' % (new_rating))
    if new_gps:
        command.append('-c')
        command.append('%.6f')
        command.append('-GPSLatitude="%f"' % (abs(new_gps.latitude)))
        command.append('-GPSLatitudeRef=' + new_gps.latitude_ref())
        command.append('-GPSLongitude="%f"' % (abs(new_gps.longitude)))
        command.append('-GPSLongitudeRef=' + new_gps.longitude_ref())
    if new_rectangles:
        if image_width > 0:
            command.append('-RegionAppliedToDimensionsW=%d' % (image_width))
        if image_height > 0:
            command.append('-RegionAppliedToDimensionsH=%d' % (image_height))
        command.append('-RegionAppliedToDimensionsUnit=pixel')
    if new_persons:
        for person in new_persons:
            command.append(u'-RegionName=%s' % (person))
            command.append(u'-RegionType=Face')
    elif new_persons != None:
        command.append('-RegionName=')
    if new_rectangles:
        for rectangle in new_rectangles:
            command.append('-RegionAreaX=%s' % (str(rectangle[0])))
            command.append('-RegionAreaY=%s' % (str(rectangle[1])))
            command.append('-RegionAreaW=%s' % (str(rectangle[2])))
            command.append('-RegionAreaH=%s' % (str(rectangle[3])))
        command.append('-RegionAreaUnit=normalized')

    elif new_rectangles != None:
        command.append('-RegionAreaX=')
    command.append("-iptc:CodedCharacterSet=ESC % G")
    command.append(filepath)
    result = su.fsdec(su.execandcombine(command))
    if tmp:
        os.remove(tmp)
    if result.find("1 image files updated") != -1:
        if result != "1 image files updated":
            su.pout(result)
           
        # wipe out the back file created by exiftool
        backup_file = filepath + "_original"
        if os.path.exists(backup_file):
            os.remove(backup_file)
        return True
    else:
        su.perr("Failed to update IPTC data in image %s: %s" % (
            filepath, result))
        return False

def _write_caption_file(new_caption, command):
    """If new_caption is set, write it into a tempory file, add a parameter to
       command, and return the file handle."""
    if new_caption is None:
        return None
    if not new_caption:
        command.append('-Caption-Abstract=')
        command.append('-ImageDescription=')
        return None
    tmpfd, tmp = tempfile.mkstemp(dir="/var/tmp")
    os.close(tmpfd)
    file1 = open(tmp, "w")
    file1.write(new_caption.encode("utf-8"))
    file1.close()
    command.append('-Caption-Abstract<=%s' % (tmp))
    command.append('-ImageDescription<=%s' % (tmp))
    return tmp
    
