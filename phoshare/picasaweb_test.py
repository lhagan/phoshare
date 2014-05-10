"""This module tests picasaweb.py."""

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
import unittest

import phoshare.picasaweb as picasaweb

class PicasawebTest(unittest.TestCase):

    def test_get_picasaweb_date(self):
        # TODO(tilmansp): This will probably fail outside of PDT
        date1 = datetime.datetime(2010, 4, 30, 12, 30, 0)
        self.assertEqual(picasaweb.get_picasaweb_date(date1), '1272655800000')
        date2 = datetime.datetime(1930, 4, 30, 12, 31, 0)
        self.assertEqual(picasaweb.get_picasaweb_date(date2), '28800000')


if __name__ == '__main__':
    unittest.main()
