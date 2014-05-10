"""This module tests appledata/iphotodata.py."""

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

import unittest

import appledata.iphotodata as iphotodata

class IPhotoDataTest(unittest.TestCase):
    """Unit tests for iphotodata.py code."""

    def test_parse_face_rectangle(self):
        """Tests iphotodata.parse_face_rectangle()."""
        self.assertEquals([0.659722, 0.752739, 0.0888889, 0.100156],
                          iphotodata.parse_face_rectangle(
                              '{{0.659722, 0.752739}, {0.0888889, 0.100156}}'))
        self.assertEquals([0.148611, 0.791862, 0.075, 0.08450710],
                          iphotodata.parse_face_rectangle(
                              '{{0.148611, 0.791862}, {0.075, 0.0845071}}'))
        self.assertEquals([0.4, 0.4, 0.2, 0.2],
                          iphotodata.parse_face_rectangle('xxyy'))

    def test_get_aperture_master_path(self):
        self.assertEquals(iphotodata._get_aperture_master_path(
            '/Volumes/Backup750/Aperture Library.aplibrary/Previews/'
            '2010/11/25/20101125-003412/OG0AGTAUSb++CJcsdH74%A/'
            '20090213 Faria Valentine - 09.jpg'),
            '/Volumes/Backup750/Aperture Library.aplibrary/'
            'Masters/2010/11/25/20101125-003412')

if __name__ == '__main__':
    unittest.main()
