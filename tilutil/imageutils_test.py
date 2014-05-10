"""This module tests imageutils.py."""

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
#   limitations under the License.'''

import datetime
import unittest
import tilutil.imageutils as iu
            
class ImageUtilsTest(unittest.TestCase):

    class TestImage(object):

        def __init__(self, caption, comment):
            self.caption = caption
            self.comment = comment
            self.date = None
            self.event_name = None
            self.event_index = None
            self.event_index0 = None

        def getfaces(self):
            return []

    class TestAlbum(object):

        def __init__(self, name, date):
            self.name = name
            self.date = date

        def getfolderhint(self):
            return 'hint'

    def test_make_foldername(self):
        self.assertEqual(iu.make_foldername('  tr im  '), 'tr im')
        self.assertEqual(iu.make_foldername('ab01, -:.'), 'ab01, -..')
        self.assertEqual(iu.make_foldername('()a[]b{}c/'), '__a__b__c_')

    def test_gps_composite(self):
        gps = iu.GpsLocation().from_composite("37.645267 N", "122.419373 W")
        self.assertEqual(37.645267, gps.latitude)
        self.assertEqual(-122.419373, gps.longitude)
        
        gps = iu.GpsLocation().from_composite("37.645267 S", "122.419373 E")
        self.assertEqual(-37.645267, gps.latitude)
        self.assertEqual(122.419373, gps.longitude)
        
        gps = iu.GpsLocation().from_composite("37.645267", "122.419373")
        self.assertEqual(37.645267, gps.latitude)
        self.assertEqual(122.419373, gps.longitude)
        
        gps = iu.GpsLocation().from_composite("-37.645267", "-122.419373")
        self.assertEqual(-37.645267, gps.latitude)
        self.assertEqual(-122.419373, gps.longitude)
    
    def test_gps_get(self):
        gps = iu.GpsLocation(37.645267, -122.419373)
        self.assertEqual(37.645267, gps.latitude)
        self.assertEqual("N", gps.latitude_ref())
        self.assertEqual(-122.419373, gps.longitude)
        self.assertEqual("W", gps.longitude_ref())
        
        gps = iu.GpsLocation(-37.645267, 122.419373)
        self.assertEqual(-37.645267, gps.latitude)
        self.assertEqual("S", gps.latitude_ref())
        self.assertEqual(122.419373, gps.longitude)
        self.assertEqual("E", gps.longitude_ref())

    def test_compare_keywords(self):
        # Two empty lists.
        self.assertTrue(iu.compare_keywords([], []))
        self.assertFalse(iu.compare_keywords([], ['a']))
        self.assertFalse(iu.compare_keywords(['a'], []))
        self.assertFalse(iu.compare_keywords(['a'], ['b']))
        # Order doesn't matter.
        self.assertTrue(iu.compare_keywords(['a', 'b'], ['b', 'a']))
        # White space does not matter.
        self.assertTrue(iu.compare_keywords([' a', 'b '], [' b', 'a ']))

    def test_get_photo_caption(self):
        template = "-{title}-"
        image = self.TestImage('x', 'y')
        self.assertEqual(iu.get_photo_caption(image, template),
                         '-x-')
        
        template = "-{description}-"
        image = self.TestImage('x', 'y')
        self.assertEqual(iu.get_photo_caption(image, template),
                         '-y-')
        
        #template = "{dated_caption_description}"
        #image = self.TestImage('x', 'y')
        #self.assertEqual(iu.get_photo_caption(image, template),
        #                 'x: y')
        #image = self.TestImage('x', '')
        #self.assertEqual(iu.get_photo_caption(image, template),
        #                 'x')
        #image = self.TestImage('x', None)
        #self.assertEqual(iu.get_photo_caption(image, template),
        #                 'x')
        #image = self.TestImage('20100510 Hello', 'y')
        #self.assertEqual(iu.get_photo_caption(image, template),
        #                 '2010/05/10 Hello: y')
        #image = self.TestImage('20100511 Hello - 31', 'y')
        #self.assertEqual(iu.get_photo_caption(image, template),
        #                 '2010/05/11 Hello: y')
        #image = self.TestImage('20100500 Hello - 31', 'y')
        #self.assertEqual(iu.get_photo_caption(image, template),
        #                 '2010/05 Hello: y')
        #image = self.TestImage('20100000 Hello - 31', 'y')
        #self.assertEqual(iu.get_photo_caption(image, template),
        #                 '2010 Hello: y')

        image = self.TestImage('x', 'y')
        self.assertEqual('//', iu.get_photo_caption(image, '{yyyy}/{mm}/{dd}'))

        image.date = datetime.datetime(2010, 12, 26, 11, 33, 15)
        self.assertEqual('2010/12/26', iu.get_photo_caption(image, '{yyyy}/{mm}/{dd}'))

        image = self.TestImage('tttt', 'dddd')
        self.assertEqual('tttt: dddd', iu.get_photo_caption(image, '{title_description}'))

        image = self.TestImage('tttt', '')
        self.assertEqual('tttt', iu.get_photo_caption(image, '{title_description}'))

        # Bad template.
        self.assertEqual('{badfield}', iu.get_photo_caption(image, '{badfield}'))


    def test_format_album_name(self):
        album = self.TestAlbum('nnnn', datetime.datetime(2010, 12, 26, 11, 33, 12))
        self.assertEqual(
            u'2010/12/26 hint nnnn',
            iu.format_album_name(album, album.name, '{yyyy}/{mm}/{dd} {hint} {album}'))
        self.assertEqual(
            u'2010/12/26 hint nnnn',
            iu.format_album_name(album, album.name, '{yyyy}/{mm}/{dd} {hint} {name}'))

        # Bad template.
        self.assertEqual('{badfield}', iu.format_album_name(album, album.name, '{badfield}'))
        

    def test_format_photo_name(self):
        image = self.TestImage('tttt', 'dddd')
        image.event_name = 'eeee'
        image.event_index = 2
        image.event_index0 = '02'
        image.date = datetime.datetime(2010, 12, 26, 11, 33, 12)
        self.assertEqual(
            u'2010-12-26 aaaa eeee tttt 5 05 2 02',
            iu.format_photo_name(image, 'aaaa', 5, '05', 
                                 ('{yyyy}/{mm}-{dd} {album} {event} {title} '
                                  '{index} {index0} {event_index} {event_index0}')))
        # Bad template
        self.assertEqual(' badfield ', iu.format_photo_name(image, 'aaaa', 5, '05', '{badfield}'))


if __name__ == "__main__":
    unittest.main()
