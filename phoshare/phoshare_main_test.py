"""This module tests phoshare_main.py."""

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

import phoshare.phoshare_main as pm

class PhoshareMainTest(unittest.TestCase):
    """Unit tests for phoshare_main.py code."""

    def test_region_matches(self):
        """Tests phoshare_main.region_matches."""
        max_same = 0.00000009
        self.assertTrue(pm.region_matches([], []))
        self.assertTrue(pm.region_matches([1, 2, 3, 4], [1, 2, 3, 4]))
        self.assertTrue(pm.region_matches([1, 2, 3, 4],
                                                [1.0 + max_same,
                                                 2.0 + max_same,
                                                 3.0 + max_same,
                                                 4.0 + max_same]))
        
        self.assertFalse(pm.region_matches([1, 2, 3, 4],
                                                 [1, 2, 3, 4.00000011]))
        self.assertFalse(pm.region_matches([1, 2, 3, 4], [1, 2, 3, 5]))
        self.assertFalse(pm.region_matches([1, 2, 3], [1, 2, 3, 4]))
        self.assertFalse(pm.region_matches([1, 2, 3], []))
        self.assertFalse(pm.region_matches([], [1, 2, 3]))

    def test_resolve_alias(self):
        """Tests phoshare_main.resolve_alias."""
        self.assertEquals("/usr", pm.resolve_alias("/usr"))
        self.assertEquals("/private/tmp", pm.resolve_alias("/tmp"))

if __name__ == '__main__':
    unittest.main()
