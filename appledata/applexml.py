'''Reads iPhoto or iTunes XML data files'''

# Original work Copyright 2010 Google Inc.
# Modified work Copyright 2014 Luke Hagan
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

# Modifications to original source by Luke Hagan:
#
#   2014-06-04: retrieve keywords from iPhoto database using sqlite
#
   
import calendar
import datetime
import unicodedata
import sys
from xml import sax
import sqlite3

import tilutil.systemutils as su

APPLE_BASE = calendar.timegm((2001, 1, 1, 0, 0, 0, 0, 0, -1))
APPLE_BASE2 = datetime.datetime.fromtimestamp(calendar.timegm((2001, 1, 1, 0, 0, 0)))


def getappletime(value):
    '''Converts a numeric Apple time stamp into a date and time'''
    try:
        # datetime.datetime.fromtimestamp() takes only int, which limits it to 12/13/1901
        # as the earliest possible date. Use an alternate calculation for earlier dates.
        # This one however adjusts for daylight savings time, so summer times are off by an
        # hour from the time recorded in iPhoto.
        if APPLE_BASE + float(value) < -sys.maxint:
            return APPLE_BASE2 + datetime.timedelta(seconds=float(value))
        return datetime.datetime.fromtimestamp(APPLE_BASE + float(value))
    except (TypeError, ValueError) as _e:
        # bad time stamp in database, default to "now"
        return datetime.datetime.now()

class AppleXMLResolver(sax.handler.EntityResolver): #IGNORE:W0232
    '''Helper to deal with XML entity resolving'''

    def __init__(self):
        pass

    def resolveEntity(self, _publicId, systemId): #IGNORE:C0103
        '''Simple schema, resolve all entities to just the systemId'''
        return systemId
    
class AppleXMLHandler(sax.handler.ContentHandler):
    '''Parses an Apple XML file, as generated by iPhoto and iTunes'''
     
    def __init__(self):
        sax.handler.ContentHandler.__init__(self)
        self.chars = ""
        self.key = None
        self.parse_stack = []
        self.top_node = None
        self._parsingdata = False
   
    def add_object(self, xml_object):
        '''Adds an object to the current container, which can be a list or a
        map.
        '''
        current_top = self.parse_stack[-1]
        if isinstance(current_top, list):
            current_top.append(xml_object)
        else:
            current_top[self.key] = xml_object
     
    def startElement(self, name, _attributes): #IGNORE:C0103
        '''Handles the start of an XML element'''
        self._parsingdata = False
        if name in ("key", "date", "string", "integer", "real", "false",
                    "true"):
            self.chars = None
        elif name == "dict":
            new_dict = {}
            self.add_object(new_dict)
            self.parse_stack.append(new_dict)
            self.chars = None
        elif name == "array":
            new_array = []
            self.add_object(new_array)
            self.parse_stack.append(new_array)
            self.chars = None
        elif name == "plist":
            self.parse_stack.append([])
            self.chars = None
        elif name == "data":
            self.chars = None
            self._parsingdata = True
        else:
            print "unrecognized element in XML data: " + name
     
    def characters(self, data):
        '''Process a character string from the SAX parser.'''
        # if we are inside a <data> element, we need to strip the characters.
        # Here is a typical <data> element:
        #   <data>
        #   AQEAAwAAAAIAAAAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
        #   AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
        #   AAAAAA==
        #   </data>
        if self._parsingdata:
            data = data.strip()
        if not self.chars:
            self.chars = data
        else:
            self.chars += data

    def endElement(self, name): #IGNORE:C0103
        '''callback for the end of a parsed XML element'''
        if name == "key":
            self.key = self.chars
        elif name == 'string':
            self.add_object(
                unicodedata.normalize("NFC", su.unicode_string(self.chars)))
        elif name in ("integer", "real", "date"):
            self.add_object(self.chars)
        elif name == "true":
            self.add_object(True)
        elif name == "false":
            self.add_object(False)
        elif name == "data":
            self.add_object(self.chars)
        elif name == "dict" or name == "array":
            self.parse_stack.pop()
        elif name == "plist":
            self.top_node = self.parse_stack.pop()
        else:
            print "unrecognized element in XML data: " + name
        self.chars = None
   
    def gettopnode(self):
        '''Returns the root of the parsed data tree'''
        return self.top_node[0]

def read_applexml(filename, sql_filename):
    '''Reads the named file, and parses it as an Apple XML file. Returns the
    top node. Replaces bad characters in the input file. Sometimes AlbumData.xml
    contains 0x00 characters!'''
    f = open(filename, buffering=16384)
    data = f.read().replace('\000', '')
    f.close()
    return read_applexml_string(data, sql_filename)

def read_applexml_string(data, sql_filename):
    '''Parses the data as Apple XML format. Returns the top node.'''
    #parser = sax.make_parser()
    handler = AppleXMLHandler()
    #parser.setContentHandler(handler)
    #parser.setEntityResolver(AppleXMLResolver())
    sax.parseString(data, handler)
    album_xml = handler.gettopnode()
    
    if sql_filename:
        # keywords are no longer available in XML
        # quick hack to pull them out of the sqlite database instead
        conn = sqlite3.connect(sql_filename)
        c = conn.cursor()
        photos = album_xml['Master Image List']
        for key in photos:
            photo = photos[key]
        
            if 'Keywords' not in photo:
                photo['Keywords'] = []
        
            c.execute('select keywordId from RKKeywordForVersion where versionId is ?', (key,))
            for keyword in c.fetchall():
                if keyword:
                    photo['Keywords'].append(keyword[0])
    
        album_xml['List of Keywords'] = {}
        c.execute('select modelId, name from RKKeyword')
        for keyword in c.fetchall():
            album_xml['List of Keywords'][keyword[0]] = keyword[1]
    
    return album_xml

