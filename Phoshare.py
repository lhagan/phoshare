#!/usr/bin/env python
"""Reads iPhoto library info, and exports photos and movies."""

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

import phoshare.phoshare_ui
import phoshare.phoshare_main

def main():
    """Main routine for Phoshare. Decides on UI vs. non-UI version."""
    if len(sys.argv) <= 1:
        phoshare.phoshare_ui.main()
    else:
        phoshare.phoshare_main.main()

if __name__ == "__main__":
    main()
