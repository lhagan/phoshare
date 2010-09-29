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

import datetime
import os
import sys
import tempfile
import time

from xml.dom import minidom
from xml import parsers

import systemutils as su

EXIFTOOL = "exiftool"

def check_exif_tool(msgstream=sys.stderr):
    """Tests if a compatible version of exiftool is available."""
    try:
        output = su.execandcombine((EXIFTOOL, "-ver"))
        version = float(output)
        if version < 7.47:
            print >> msgstream, "You have version " + str(version) + " of exiftool."
            print >> msgstream, """
Please upgrade to version 7.47 or newer of exiftool. You can download a copy
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
        if (xml_element.firstChild.nodeValue and
            xml_element.firstChild.nodeValue != "\n"):
            data.append(xml_element.firstChild.nodeValue)
        for xml_bag in xml_element.getElementsByTagName("rdf:Bag"):
            for xml_li in xml_bag.getElementsByTagName("rdf:li"):
                data.append(xml_li.firstChild.nodeValue)

def get_iptc_data(image_file):
    """get caption, keywords, datetime, rating, and GPS info all in one 
       operation."""
    output = su.execandcombine(
        (EXIFTOOL, "-X", "-m", "-q", "-q", '-c', '%.6f', "-Keywords", 
         "-Caption-Abstract", "-DateTimeOriginal", "-Rating", "-GPSLatitude",
         "-Subject", "-GPSLongitude", "-RegionRectangle",
         "-RegionPersonDisplayName", "%s" % (image_file.encode('utf8'))))
  
    keywords = []
    caption = None
    date_time_original = None
    rating = 0
    gps = None
    region_names = []
    region_rectangles = []
    if output:
        try:
            gps_latitude = None
            gps_longitude = None

            xml_data = minidom.parseString(output)
        
            for xml_desc in xml_data.getElementsByTagName("rdf:Description"):
                _get_xml_nodevalues(xml_desc, "IPTC:Keywords", keywords)
                # Keywords can also be stored as Subject in the XMP directory
                _get_xml_nodevalues(xml_desc, "XMP:Subject", keywords)
                for xml_caption in xml_data.getElementsByTagName(
                    "IPTC:Caption-Abstract"):
                    caption = xml_caption.firstChild.nodeValue
                for xml_element in xml_data.getElementsByTagName(
                    "ExifIFD:DateTimeOriginal"):
                    if not xml_element.firstChild:
                        continue
                    try:
                        date_time_original = time.strptime(xml_element.firstChild.nodeValue,
                                                           "%Y:%m:%d %H:%M:%S")
                        date_time_original = datetime.datetime(
                            date_time_original.tm_year,
                            date_time_original.tm_mon,
                            date_time_original.tm_mday,
                            date_time_original.tm_hour,
                            date_time_original.tm_min,
                            date_time_original.tm_sec)
                    except ValueError, _ve:
                        print >> sys.stderr, ("Exiftool returned an invalid date %s for %s - "
                                              "ignoring.") % (
                            xml_element.firstChild.nodeValue, image_file)
                for xml_element in xml_data.getElementsByTagName("XMP-xmp:Rating"):
                    rating = int(xml_element.firstChild.nodeValue)
                for xml_element in xml_data.getElementsByTagName(
                    "Composite:GPSLatitude"):
                    gps_latitude = xml_element.firstChild.nodeValue
                for xml_element in xml_data.getElementsByTagName(
                    "Composite:GPSLongitude"):
                    gps_longitude = xml_element.firstChild.nodeValue
                string_rectangles = []
                _get_xml_nodevalues(xml_desc, 'XMP-MP:RegionRectangle', string_rectangles)
                for string_rectangle in string_rectangles:
                    rectangle = []
                    for c in string_rectangle.split(','):
                        rectangle.append(float(c))
                    region_rectangles.append(rectangle)
                _get_xml_nodevalues(xml_desc, 'XMP-MP:RegionPersonDisplayName', region_names)

            xml_data.unlink()
            if gps_latitude and gps_longitude:
                latitude = float(gps_latitude[0:-2])
                if gps_latitude.endswith(" S"):
                    latitude = -latitude
                longitude = float(gps_longitude[0:-2])
                if gps_longitude.endswith(" W"):
                    longitude = -longitude
                gps = (latitude, longitude)
        except parsers.expat.ExpatError, ex:
            print >> sys.stderr, "Could not parse exiftool output %s: %s" % (
                output, ex)

    return (keywords, caption, date_time_original, rating, gps,
            region_rectangles, region_names)


def update_iptcdata(filepath, new_caption, new_keywords, new_datetime, 
                    new_rating, new_gps, new_rectangles, new_persons): 
    """Updates the caption and keywords of an image file."""
    # Some cameras write into ImageDescription, so we wipe it out to not cause
    # conflicts with Caption-Abstract. We also wipe out the XMP Subject and Description
    # tags (we use Keywords and Caption-Abstract).
    command = [EXIFTOOL, '-F', '-ImageDescription=', '-Subject=', '-Description=']
    tmp = None
    if not new_caption is None:
        tmpfd, tmp = tempfile.mkstemp(dir="/var/tmp")
        os.close(tmpfd)
        file1 = open(tmp, "w")
        if not new_caption:
            # you can't set caption to an empty string
            new_caption = " "
        print >> file1, new_caption.encode("utf-8")
        file1.close()
        command.append('-Caption-Abstract<=%s' % (tmp))
    
    if new_datetime:
        command.append('-DateTimeOriginal="%s"' % (
            new_datetime.strftime("%Y:%m:%d %H:%M:%S")))
    if new_keywords:
        for keyword in new_keywords:
            command.append(u'-keywords=%s' % (keyword))
    elif new_keywords != None:
        command.append('-keywords=')
    if new_rating >= 0:
        command.append('-Rating=%d' % (new_rating))
    if new_gps:
        command.append('-c')
        command.append('%.6f')
        latitude = float(new_gps[0])
        command.append('-GPSLatitude="%f"' % (abs(latitude)))
        if latitude >= 0.0:
            command.append('-GPSLatitudeRef=N')
        else:
            command.append('-GPSLatitudeRef=S')
        longitude = float(new_gps[1])
        command.append('-GPSLongitude="%f"' % (abs(longitude)))
        if longitude >= 0.0:
            command.append('-GPSLongitudeRef=E')
        else:
            command.append('-GPSLongitudeRef=W')
    if new_persons:
        for person in new_persons:
            command.append(u'-RegionPersonDisplayName=%s' % (person))
    elif new_persons != None:
        command.append('-RegionPersonDisplayName=')
    if new_rectangles:
        for rectangle in new_rectangles:
            command.append('-RegionRectangle=%s' % (','.join(str(c) for c in rectangle)))
    elif new_rectangles != None:
        command.append('-RegionRectangle=')
    command.append("-iptc:CodedCharacterSet=ESC % G")
    command.append(filepath)
    result = su.execandcombine(command)
    if tmp:
        os.remove(tmp)
    if result == "1 image files updated":
        # wipe out the back file created by exiftool
        backup_file = filepath + "_original"
        if os.path.exists(backup_file):
            os.remove(backup_file)
        return True
    else:
        print >> sys.stderr, "Failed to update IPTC data in image %s: %s" % (
            su.fsenc(filepath), result)
        return False
    
