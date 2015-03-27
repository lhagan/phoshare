# Notice

Due to Apple's discontinuation of iPhoto in favor of the new Photos app, I'm no longer maintaining this fork of phoshare.

# Overview

`phoshare` allows you to export and synchronize your iPhoto library to a folder tree. It preserves both the original and modified image, your event and album organization, and applies your iPhoto titles, descriptions, keywords, face tags, face rectangles, places, and ratings to the IPTC/EXIF metadata of your images. You can export a full copy of your library, or just build a tree of linked images that require very little additional disk space. You can re-run `phoshare` at any time to synchronize any changes made in iPhoto to your export tree quickly. `phoshare` works well with file-system based photo management tools like Picasa, Adobe Bridge, or Windows Live Photo Gallery.

[Dan Warne](http://danwarne.com/) has written a blog post on [how to back up your iPhoto library to Dropbox](http://danwarne.com/backup-iphoto-library-dropbox-resize-images-save-space-2/) with `phoshare`.

`phoshare` is written in Python, and is easily customizable by just editing the Python scripts.

This fork is intended to revive `phoshare` as the original author [discontinued development](https://groups.google.com/forum/?fromgroups=#!topic/phoshare-users/moWsMcD5SdQ) in late 2012. It's meant for use with the latest version of iPhoto (9.5.1 as of this writing). It also drops Aperture support for the sake of simplicity (and because I don't have Aperture). For older versions of iPhoto and any version of Aperture, please use an earlier version from the original [project](https://code.google.com/p/phoshare/downloads/list).

# Documentation

For now, use the original [Documentation](https://sites.google.com/site/phosharedoc) link for "How To" information, and the [user group](http://groups.google.com/group/phoshare-users) for additional information. I will update the documentation for the fork as time permits.

# License

Original work Copyright 2010 Google Inc.
Modified work Copyright 2014 Luke Hagan

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
