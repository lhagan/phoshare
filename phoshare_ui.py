#! /usr/bin/env python
"""Reads iPhoto library info, and exports photos and movies. GUI version."""

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

import os
import threading
import tkFileDialog
import tkMessageBox

# pylint: disable-msg=W0614
from Tkinter import *  #IGNORE:W0401

import appledata.iphotodata as iphotodata
import Phoshare
import tilutil.exiftool as exiftool
import tilutil.systemutils as su

from ScrolledText import ScrolledText

import ConfigParser
import Queue

_PHOSHARE_VERSION = 'Phoshare 1.0'
_CONFIG_PATH = su.expand_home_folder('~/Library/Application Support/Google/'
                                     'Phoshare/phoshare.cfg')

def _int_from_bool(boolean_value):
    """Converts a boolean value to an integer of 0 or 1."""
    if boolean_value:
        return 1
    return 0

class HelpDialog(Toplevel):
    """Displays a help dialog, using a scrolled text area."""

    def __init__(self, parent, text, title="Phoshare Help"):
        Toplevel.__init__(self, parent)
        self.transient(parent)
        self.title(title)
        self.parent = parent
        t = ScrolledText(self)
        t.insert(END, text)
        t.config(state=DISABLED)
        t.pack()

class ExportApp(Frame):
    """GUI version of the phoshare tool."""

    def __init__(self, master=None):
        """Initialize the app, setting up the UI."""
        Frame.__init__(self, master, bd=10)

        top = self.winfo_toplevel()
        menuBar = Menu(top)
        top["menu"] = menuBar
        
        subMenu = Menu(menuBar)
        menuBar.add_cascade(label="Help", menu=subMenu)
        subMenu.add_command(label="About Phoshare", command=self.__aboutHandler)

        self.thread_queue = Queue.Queue(maxsize=100)
        self.active_library = None
        
        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)
        self.grid(sticky=N+S+E+W)

        self.valid_library = False
        self.exiftool = False

        self.iphoto_library = StringVar()
        self.iphoto_library_status = StringVar()
        self.browse_library_button = None
        self.export_folder = StringVar()

        self.library_status = None
        self.dryrun_button = None
        self.export_button = None
        self.text = None

        self.events = StringVar()
        self.albums = StringVar()
        self.smarts = StringVar()

        self.update_var = IntVar()
        self.delete_var = IntVar()
        self.originals_var = IntVar()
        self.link_var = IntVar()
        self.folder_hints_var = IntVar()
        self.faces_var = IntVar()
        self.face_keywords_var = IntVar()
        self.face_albums_var = IntVar()
        self.face_albums_text = StringVar()

        self.iptc_var = IntVar()
        self.iptc_all_var = IntVar()

        self.gps_var = IntVar()

        self.create_widgets()

    def __aboutHandler(self):
        HelpDialog(self, """       %s

  Copyright 2010 Google Inc.

http://code.google.com/p/phoshare""" % (_PHOSHARE_VERSION),
                   title="About Phoshare")

    def init(self):
        """Initializes processing by launching background thread checker and 
           initial iPhoto library check."""
        self.thread_checker()
        if exiftool.check_exif_tool(sys.stdout):
            self.exiftool = True
            self.faces_box.configure(state=NORMAL)
            self.face_keywords_box.configure(state=NORMAL)
            self.iptc_box.configure(state=NORMAL)
            self.iptc_all_box.configure(state=NORMAL)
            self.gps_box.configure(state=NORMAL)

        options = self.Options()
        options.load()      
        self.init_from_options(options)
        self.check_iphoto_library()

    def init_from_options(self, options):
        """Populates the UI from options."""
        self.iphoto_library.set(options.iphoto)
        self.export_folder.set(options.export)
        self.albums.set(options.albums)
        self.events.set(options.events)
        self.smarts.set(options.smarts)
        self.update_var.set(_int_from_bool(options.update))
        self.delete_var.set(_int_from_bool(options.delete))
        self.originals_var.set(_int_from_bool(options.originals))
        self.link_var.set(_int_from_bool(options.link))
        self.folder_hints_var.set(_int_from_bool(options.folderhints))
        self.faces_var.set(_int_from_bool(options.faces) and self.exiftool)
        self.face_keywords_var.set(_int_from_bool(options.face_keywords) and
                                   self.exiftool)
        self.face_albums_var.set(_int_from_bool(options.facealbums))
        self.face_albums_text.set(options.facealbum_prefix)
        if options.iptc and self.exiftool:
            self.iptc_var.set(1)
            if options.iptc == 2:
                self.iptc_all_var.set(1)
        self.gps_var.set(_int_from_bool(options.gps) and self.exiftool)

    def create_widgets(self):
        """Builds the UI."""
        bold_font = ('helvetica', 12, 'bold')
        self.columnconfigure(2, weight=1)
        row = 0
        Label(self, text="iPhoto Library:").grid(sticky=E)
        iphoto_library_entry = Entry(self, textvariable=self.iphoto_library)
        iphoto_library_entry.grid(row=row, column=1, columnspan=2, sticky=E+W)
        self.browse_library_button = Button(self, text="Browse...",
                                            command=self.browse_library)
        self.browse_library_button.grid(row=row, column=3)

        row += 1
        self.library_status = Label(self, 
                                    textvariable=self.iphoto_library_status)
        self.library_status.grid(row=row, column=1, columnspan=2, sticky=W)

        row += 1
        label = Label(self, text="Events, Albums and Smart Albums")
        label.config(font=bold_font)
        label.grid(row=row, column=0, columnspan=3, sticky=W)

        Button(self, bitmap='question',
               command=self.help_events).grid(row=row, column=3, sticky=E)

        row += 1
        Label(self, text="Events:").grid(sticky=E)
        events_entry = Entry(self, textvariable=self.events)
        events_entry.grid(row=row, column=1, columnspan=3, sticky=EW)

        row += 1
        Label(self, text="Albums:").grid(sticky=E)
        albums_entry = Entry(self, textvariable=self.albums)
        albums_entry.grid(row=row, column=1, columnspan=3, sticky=EW)

        row += 1
        Label(self, text="Smart Albums:").grid(sticky=E)
        smarts_entry = Entry(self, textvariable=self.smarts)
        smarts_entry.grid(row=row, column=1, columnspan=3, sticky=EW)

        row += 1
        label = Label(self, text="Export Folder and Options")
        label.config(font=bold_font)
        label.grid(row=row, column=0, columnspan=4, sticky=W)

        Button(self, bitmap='question',
               command=self.help_export).grid(row=row, column=3, sticky=E)

        row += 1
        label = Label(self, text="Export Folder:")
        label.grid(sticky=E)
        export_folder_entry = Entry(self, textvariable=self.export_folder)
        export_folder_entry.grid(row=row, column=1, columnspan=2, sticky=E+W)
        Button(self, text="Browse...", 
               command=self.browse_export).grid(row=row, column=3)

        row += 1
        update_box = Checkbutton(self, text="Overwrite changed pictures", 
                                 var=self.update_var)
        update_box.grid(row=row, column=1, sticky=W)
        originals_box = Checkbutton(self, text="Export originals", 
                                    var=self.originals_var)
        originals_box.grid(row=row, column=2, sticky=W)
        hint_box = Checkbutton(self, text="Use folder hints", 
                               var=self.folder_hints_var)
        hint_box.grid(row=row, column=3, sticky=W)

        row += 1
        delete_box = Checkbutton(self, text="Delete obsolete pictures", 
                                 var=self.delete_var)
        delete_box.grid(row=row, column=1, sticky=W)
        link_box = Checkbutton(self, text="Use file links", var=self.link_var)
        link_box.grid(row=row, column=2, columnspan=2, sticky=W)

        row += 1
        label = Label(self, text="Faces")
        label.config(font=bold_font)
        label.grid(row=row, column=0, columnspan=4, sticky=W)
        Button(self, bitmap='question',
               command=self.help_faces).grid(row=row, column=3, sticky=E)

        row += 1
        self.faces_box = Checkbutton(self, text="Copy faces into metadata", 
                                     var=self.faces_var, state=DISABLED,
                                     command=self.change_metadata_box)
        self.faces_box.grid(row=row, column=1, sticky=W)

        self.face_keywords_box = Checkbutton(self, 
                                             text="Copy face namess into keywords", 
                                             var=self.face_keywords_var,
                                             command=self.change_metadata_box,
                                             state=DISABLED)
        self.face_keywords_box.grid(row=row, column=2, columnspan=2, sticky=W)

        row += 1
        checkbutton = Checkbutton(self, text="Export faces into folders", 
                                  var=self.face_albums_var)
        checkbutton.grid(row=row, column=1, sticky=W)
        label = Label(self, text="Faces folder prefix:")
        label.grid(row=row, column=2, sticky=E)
        entry = Entry(self, textvariable=self.face_albums_text)
        entry.grid(row=row, column=3, sticky=E+W)

        row += 1
        label = Label(self, text="Metadata")
        label.config(font=bold_font)
        label.grid(row=row, column=0, columnspan=4, sticky=W)

        Button(self, bitmap='question',
               command=self.help_metadata).grid(row=row, column=3, sticky=E)

        row += 1
        self.iptc_box = Checkbutton(self,
                                    text=("Export metadata (descriptions, "
                                          "keywords, ratings, dates)"),
                                    var=self.iptc_var, state=DISABLED,
                                    command=self.change_iptc_box)
        self.iptc_box.grid(row=row, column=1, columnspan=3, sticky=W)

        row += 1
        self.iptc_all_box = Checkbutton(self,
                                        text="Verify existing images",
                                        var=self.iptc_all_var,
                                        command=self.change_metadata_box,
                                        state=DISABLED)
        self.iptc_all_box.grid(row=row, column=1, sticky=W)

        self.gps_box = Checkbutton(self,
                                   text="Export GPS data",
                                   var=self.gps_var,
                                   command=self.change_metadata_box,
                                   state=DISABLED)
        self.gps_box.grid(row=row, column=2, sticky=W)

        row += 1
        self.dryrun_button = Button(self, text="Dry Run", 
                                    command=self.do_dryrun, state=DISABLED)
        self.dryrun_button.grid(row=row, column=2, stick=E, pady=5)
        self.export_button = Button(self, text="Export", 
                                    command=self.do_export, state=DISABLED)
        self.export_button.grid(row=row, column=3, pady=5)

        row += 1
        self.text = ScrolledText(self, borderwidth=4, relief=RIDGE, padx=4,
                                 pady=4)
        self.text.grid(row=row, column=0, columnspan=4, sticky=E+W+N+S)
        self.rowconfigure(row, weight=1)

    def change_iptc_box(self):
        """Clears some options that depend on the metadata export option."""
        mode = self.iptc_var.get()
        if not mode:
            self.faces_var.set(0)
            self.face_keywords_var.set(0)
            self.iptc_all_var.set(0)
            self.gps_var.set(0)

    def change_metadata_box(self):
        """Sets connected options if an option that needs meta data is changed."""
        mode = (self.faces_var.get() or self.face_keywords_var.get() or
                self.iptc_all_var.get() or self.gps_var.get())
        if mode:
            self.iptc_var.set(1)
            
    def help_events(self):
        HelpDialog(self, """Events, Albums and Smart Albums

Selects which events, albums, or smart albums to export.

Each field is a regular expression, and at least one must be filled in.
Matches are done against the beginning of the event or album name. An
entry in Events of
    Family
will export all events that start with "Family", including "Family 2008"
and "Family 2009". "|" separates alternate patterns, so
    Family|Travel
will export all events that start with either "Family" or "Travel".

"." matches any character, and therefore,
    .
will export all events. To export all events with "2008" in the name, use
    .*2008

For more details on regular expressions, see
    http://en.wikipedia.org/wiki/Regular_expression""")
        
    def help_export(self):
        HelpDialog(self, """Export Settings

Export Folder: path to the folder for exporting images.

Overwrite changed pictures: If set, pictures that already exist in the export
                            folder will be overriden if an different version
                            exist in iPhoto. Any edits made to previously
                            exported images in the export folder will be lost!
                            Use Dry Run to see which files would be overwritten.

Export originals: If set, and an image has been modified in iPhoto, both the
                  original and the edited version will be exported. The original
                  will be stored in a sub-folder called "Originals".

Use folder hints: By default, each exported event or album will become a folder
                  in the export folder. With folder hints, a sub-folder name can
                  be given in the event or album description by adding a line
                  starting with a @ character. Example:
                      Family Vacation
                      @Vacation
                  would export all images in that event into a sub-folder called
                  "Vacation".

Delete obsolete pictures: If set, any image, movie file or folder in the export
                          folder that does not exist in the iPhoto library will
                          be deleted. Use Dry Run to see which files would be
                          deleted.

Use file links: Don't copy images during export, but make a link to the files
                in the iPhoto library instead. This option is only available
                if the export folder is on the same drive as the iPhoto library.
                This option will save a lot of disk space because it avoids
                making copies of all your images and videos. Using this option
                causes the metadata of the images IN YOUR IPHOTO LIBRARY to be
                modified. While phoshare should not cause any problems to your
                images, it is best to use this option only if you have a backup
                of your iPhoto library, and you know how to restore your library
                from the backup. For more details on link mode, see
                https://sites.google.com/site/phosharedoc/Home#TOC-link-mode""")
        
    def help_faces(self):
        HelpDialog(self, """Faces options.

Copy faces into metadata: faces tags and face regions will be copied into the
                          image metadata using the Microsoft Photo Region
                          Schema:
               http://msdn.microsoft.com/en-us/library/ee719905(VS.85).aspx

Copy faces names into keywords: If set, face names will be merged into image
                                keywords. Requires "Export metadata" checked.

Export faces into folders: If checked, folders will be created for each face
                           tag, each containing all the images tagged with
                           that person.

Faces folder prefix: If set, the string will be used as a prefix for the
                     face export folders if "Exported faces into folders"
                     is checked. This can be just a value like "Face: ", or
                     a sub-folder name like "Faces/" if it ends with a "/"

Metadata options will be disabled if exiftool is not available.
""")
        
    def help_metadata(self):
        HelpDialog(self, """Metadata options.

Export metadata: sets the description, keywords, rating and date metadata in the
                 exported images to match the iPhoto settings.

Verify existing images: If not checked, metadata will only be set for new or
                        updated images. If checked, metadata will be checked in
                        all images, including ones that were previously
                        exported. This is much slower.

Export GPS data: export the GPS coordinates into the image metadata.

Metadata options will be disabled if exiftool is not available.""")
        
    def check_iphoto_library(self):
        self.valid_library = False
        self.enable_buttons()
        self.iphoto_library_status.set("Checking library location...")
        self.launch_export("library")

    def set_library_status(self, good, message):
        if good:
            self.valid_library = True
            self.enable_buttons()
        self.iphoto_library_status.set(message)

    def write_progress(self, text):
        self.text.insert(END, text)
        self.text.see(END)

    def enable_buttons(self):
        if self.valid_library:
            self.dryrun_button.config(state=NORMAL)
            self.export_button.config(state=NORMAL)
        else:
            self.dryrun_button.config(state=DISABLED)
            self.export_button.config(state=DISABLED)
        self.browse_library_button.config(state=NORMAL)

    def browse_library(self):
        path = tkFileDialog.askopenfilename(title="Locate iPhoto Library")
        self.iphoto_library.set(path)
        self.check_iphoto_library()

    def browse_export(self):
        path = tkFileDialog.askdirectory(title="Locate Export Folder")
        self.export_folder.set(path)

    def do_export(self):
        if self.active_library:
            self.stop_thread()
            return
        if not self.can_export():
            return
        self.export_button.config(text="Stop Export")
        self.dryrun_button.config(state=DISABLED)
        self.run_export(False)

    def do_dryrun(self):
        if self.active_library:
            self.stop_thread()
            return
        if not self.can_export():
            return
        self.dryrun_button.config(text="Stop Dry Run")
        self.export_button.config(state=DISABLED)
        self.run_export(True)

    def stop_thread(self):
        if self.active_library:
            self.active_library.abort()
        
    def export_done(self):
        self.active_library = None
        self.dryrun_button.config(text="Dry Run")
        self.export_button.config(text="Export")
        self.enable_buttons()

    class Options(object):
        """Simple helper to create an object compatible with the OptionParser 
        output in phoshare.py."""

        def __init__(self):
            self.iphoto = '~/Pictures/iPhoto Library'
            self.export = '~/Pictures/Album'
            self.albums = ''
            self.events = '.'
            self.smarts = ''
            self.delete = False
            self.update = False
            self.link = False 
            self.dryrun = False
            self.folderhints = False
            self.nametemplate = "${caption}"
            self.size = ''  # TODO
            self.picasa = False  # TODO
            self.movies = True  # TODO
            self.originals = False
            self.iptc = 0
            self.gps = False
            self.faces = False
            self.facealbums = False
            self.facealbum_prefix = ''
            self.face_keywords = False

        def load(self):
            """Attempts to load saved options. Returns True if saved options
            were available."""
            if not os.path.exists(_CONFIG_PATH):
                return False
            config = ConfigParser.SafeConfigParser()
            config.read(_CONFIG_PATH)
            s = 'Export1'
            self.iphoto = config.get(s, 'iphoto')
            self.export = config.get(s, 'export')
            self.albums = config.get(s, 'albums')
            self.events = config.get(s, 'events')
            self.smarts = config.get(s, 'smarts')
            self.delete = config.getboolean(s, 'delete')
            self.update = config.getboolean(s, 'update')
            self.link = config.getboolean(s, 'link')
            self.folderhints = config.getboolean(s, 'folderhints')
            self.nametemplate = config.get(s, 'nametemplate')
            self.size = config.get(s, 'size')
            self.picasa = config.getboolean(s, 'picasa')
            self.movies = config.getboolean(s, 'movies')
            self.originals = config.getboolean(s, 'originals')
            self.iptc = config.getint(s, 'iptc')
            self.gps = config.getboolean(s, 'gps')
            self.faces = config.getboolean(s, 'faces')
            self.facealbums = config.getboolean(s, 'facealbums')
            self.facealbum_prefix = config.get(s, 'facealbum_prefix')
            self.face_keywords = config.getboolean(s, 'face_keywords')
            return True

        def save(self):
            """Saves the current options into a file."""
            config = ConfigParser.RawConfigParser()
            s = 'Export1'
            config.add_section(s)
            config.set(s, 'iphoto', self.iphoto)
            config.set(s, 'export', self.export)
            config.set(s, 'albums', self.albums)
            config.set(s, 'events', self.events)
            config.set(s, 'smarts', self.smarts)
            config.set(s, 'delete', self.delete)
            config.set(s, 'update', self.update)
            config.set(s, 'link', self.link)
            config.set(s, 'dryrun', self.dryrun)
            config.set(s, 'folderhints', self.folderhints)
            config.set(s, 'nametemplate', self.nametemplate)
            config.set(s, 'size', self.size)
            config.set(s, 'picasa', self.picasa)
            config.set(s, 'movies', self.movies)
            config.set(s, 'originals', self.originals)
            config.set(s, 'iptc', self.iptc)
            config.set(s, 'gps', self.gps)
            config.set(s, 'faces', self.faces)
            config.set(s, 'facealbums', self.facealbums)
            config.set(s, 'facealbum_prefix', self.facealbum_prefix)
            config.set(s, 'face_keywords', self.face_keywords)

            config_folder = os.path.split(_CONFIG_PATH)[0]
            if not os.path.exists(config_folder):
                os.makedirs(config_folder)
            configfile = open(_CONFIG_PATH, 'wb')
            config.write(configfile)
            configfile.close()

    def can_export(self):
        if (not self.albums.get() and not self.events.get() and 
            not self.smarts.get()):
            tkMessageBox.showerror(
                "Export Error",
                ("Need to specify at least one event, album, or smart album "
                 "for exporting."))
            return False
        return True

    def run_export(self, dry_run):
        mode = "export"
        if dry_run:
            mode = "dry_run"
        self.launch_export(mode)

    def launch_export(self, mode):
        """Launch an export operation in a new thread, to not block the UI.

        Args:
            mode - name of operation to run, "library", "dry_run", or "export".
        """
        self.text.delete('1.0', END)
        self.browse_library_button.config(state=DISABLED)
        export_thread = threading.Thread(target=self.export_thread,
                                         args=(mode,))
        export_thread.start()

    def export_thread(self, mode):
        """Run an export operation in a thread, to not block the UI.

        Args:
            mode - name of operation to run, "library", "dry_run", or "export".
        """
        try:
            # First, load the iPhoto library.
            library_path = su.expand_home_folder(self.iphoto_library.get())
            album_xml_file = iphotodata.get_album_xmlfile(library_path)
            data = iphotodata.get_iphoto_data(album_xml_file)
            msg = "Version %s library with %d images" % (
                data.applicationVersion, len(data.images))
            self.write(msg + '\n')
            if mode == "library":
                # If we just need to check the library, we are done here.
                self.thread_queue.put(("done", (True, mode, msg)))
                return

            # Do the actual export.
            export_folder = su.expand_home_folder(self.export_folder.get())

            options = self.Options()
            options.iphoto = self.iphoto_library.get()
            options.export = self.export_folder.get()
            options.dryrun = mode == "dry_run"
            options.albums = self.albums.get()
            options.events = self.events.get()
            options.smarts = self.smarts.get()
            options.update = self.update_var.get() == 1
            options.delete = self.delete_var.get() == 1
            options.originals = self.originals_var.get() == 1
            options.link = self.link_var.get() == 1
            options.folderhints = self.folder_hints_var.get() == 1
            options.faces = self.faces_var.get() == 1
            options.face_keywords = self.face_keywords_var.get() == 1
            if self.iptc_all_var.get() == 1:
                options.iptc = 2
            elif self.iptc_var.get() == 1:
                options.iptc = 1
            else:
                options.iptc = 0
            options.gps = self.gps_var.get()
            options.facealbums = self.face_albums_var.get() == 1
            options.facealbum_prefix = self.face_albums_text.get()
            
            exclude = None # TODO

            exclude_folders = []  # TODO

            options.save()
            self.active_library = Phoshare.ExportLibrary(export_folder)
            self.active_library.export_iphoto(data, exclude, 
                                              exclude_folders, options)
            self.thread_queue.put(("done", (True, mode, '')))
        except Exception, e:  # IGNORE:W0703
            self.thread_queue.put(("done", (False, mode, str(e))))
            print >> sys.stderr, e
        
    def thread_checker(self, delay_ms=100):        # 10x per second
        """Processes any queued up messages in the thread queue. Once the queue
        is empty, schedules another check after a short delay.

        This method runs in the main thread, and therefore, can update the UI.
        """
        writes = 0
        while True:
            try:
                (callback, args) = self.thread_queue.get(block=False)
                if callback == "write":
                    self.write_progress(args)
                    writes += 1
                    if writes >= 10:
                        # After 10 consecutive writes to the progress area,
                        # update the UI so that the user can see the progress.
                        self.update()
                        writes = 0
                    continue
                # Must be a "done" message, with a (success, mode, msg)
                # argument.
                success = args[0]
                mode = args[1]
                msg = args[2]
                if success:
                    self.write_progress("Done!")
                else:
                    self.write_progress("Error: " + msg)
                if mode == "library":
                    self.set_library_status(success, msg)
                else:
                    self.export_done()
            except Queue.Empty:
                break

        # Check the queue again after a short delay.
        self.after(delay_ms, self.thread_checker)

    def write(self, text):
        """Writes text to the progress area of the UI. Uses the thread queue,
        and can be called from a non-UI thread."""
        self.thread_queue.put(("write", str(text)))
        
    def writelines(self, lines):  # lines already have '\n'
        """Writes text to the progress area of the UI. Uses the thread queue,
        and can be called from a non-UI thread."""
        for line in lines:
            self.write(line)     


def main():
    """Main routine for phoshare_ui. Typically launched from Phoshare.py"""
    app = ExportApp()
    app.master.title(_PHOSHARE_VERSION)
    sys.stdout = app
    app.init()
    app.mainloop()

if __name__ == "__main__":
    main()
