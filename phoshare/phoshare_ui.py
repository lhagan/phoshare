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

import cStringIO
import logging
import os
import platform
import threading
import tkFileDialog
import tkMessageBox
import traceback

# pylint: disable-msg=W0614
from Tkinter import *  #IGNORE:W0401
from ttk import *

import appledata.iphotodata as iphotodata
import phoshare.phoshare_main as phoshare_main
import phoshare.phoshare_version as phoshare_version
import tilutil.exiftool as exiftool
import tilutil.systemutils as su

from ScrolledText import ScrolledText

import ConfigParser
import Queue

_CONFIG_PATH = su.expand_home_folder('~/Library/Application Support/Google/'
                                     'Phoshare/phoshare.cfg')
_BOLD_FONT = ('helvetica', 12, 'bold')

_logger = logging.getLogger('google')

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
    """GUI version of the Phoshare tool."""

    def __init__(self, master=None):
        """Initialize the app, setting up the UI."""
        Frame.__init__(self, master, padding=10)

        top = self.winfo_toplevel()
        menu_bar = Menu(top)
        top["menu"] = menu_bar

        apple = Menu(menu_bar, name='apple')
        menu_bar.add_cascade(label='Phoshare', menu=apple)
        apple.add_command(label="About Phoshare", command=self.__aboutHandler)

        sub_menu = Menu(menu_bar, name='help')
        menu_bar.add_cascade(label="Help", menu=sub_menu)
        sub_menu.add_command(label="Phoshare Help", command=self.help_buttons)

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

        self.foldertemplate = StringVar()
        self.nametemplate = StringVar()
        self.captiontemplate = StringVar()

        self.update_var = IntVar()
        self.delete_var = IntVar()
        self.originals_var = IntVar()
        self.link_var = IntVar()
        self.folder_hints_var = IntVar()
        self.faces_box = None
        self.faces_var = IntVar()
        self.face_keywords_box = None
        self.face_keywords_var = IntVar()
        self.face_albums_var = IntVar()
        self.face_albums_text = StringVar()

        self.iptc_box = None
        self.iptc_all_box = None
        self.iptc_var = IntVar()
        self.iptc_all_var = IntVar()

        self.gps_box = None
        self.gps_var = IntVar()
        self.verbose_var = IntVar()

        self.info_icon = PhotoImage(file="info-b16.gif")

        self.create_widgets()

        # Set up logging so it gets redirected to the text area in the app.
        self.logging_handler = logging.StreamHandler(self)
        self.logging_handler.setLevel(logging.WARN)
        _logger.addHandler(self.logging_handler)

    def __aboutHandler(self):
        HelpDialog(self, """%s %s

  Copyright 2010 Google Inc.

http://code.google.com/p/phoshare""" % (phoshare_version.PHOSHARE_VERSION,
	phoshare_version.PHOSHARE_BUILD),
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
        self.albums.set(su.fsdec(options.albums))
        self.events.set(su.fsdec(options.events))
        self.smarts.set(su.fsdec(options.smarts))
        self.foldertemplate.set(su.unicode_string(options.foldertemplate))
        self.nametemplate.set(su.unicode_string(options.nametemplate))
        self.captiontemplate.set(su.unicode_string(options.captiontemplate))
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

    def _add_section(self, container, text, help_command):
        """Adds a new UI section with a bold label and an info button.

        Args:
          container: UI element that will contain this new item
          row: row number in grid. Uses two rows.
          text: label frame text.
          help_command: command to run when the info button is pressed.
        Returns: tuple of new section and content frames.
        """
        section_frame = Frame(container)
        section_frame.columnconfigure(0, weight=1)
        label = Label(section_frame, text=text)
        label.config(font=_BOLD_FONT)
        label.grid(row=0, column=0, sticky=W, pady=5)
        Button(section_frame, image=self.info_icon,
               command=help_command).grid(row=0, column=1, sticky=E)

        content_frame = Frame(section_frame)
        content_frame.grid(row= 1, column=0, columnspan=2, sticky=N+S+E+W, pady=5)

        return (section_frame, content_frame)

    def _create_button_bar(self, container, row):
        """Creates the button bar with the Dry Run and Export buttons.

        Args:
          row: row number in grid.
        Returns: next row number in grid.
        """
        button_bar = Frame(container)
        button_bar.grid(row=row, column=0, sticky=E+W, padx=10)
        button_bar.columnconfigure(0, weight=1)
        verbose_box = Checkbutton(button_bar, text="Show debug output", var=self.verbose_var)
        verbose_box.grid(row=0, column=0, sticky=E)
        self.dryrun_button = Button(button_bar, text="Dry Run",
                                    command=self.do_dryrun, state=DISABLED)
        self.dryrun_button.grid(row=0, column=1, sticky=E, pady=5)
        self.export_button = Button(button_bar, text="Export",
                                    command=self.do_export, state=DISABLED)
        self.export_button.grid(row=0, column=2, pady=5)
        return row + 1

    def _create_library_tab(self, library_tab):
        library_tab.columnconfigure(0, weight=1)
        row = 0

        f = Frame(library_tab)
        f.grid(row=row, columnspan=2, stick=E+W, padx=5, pady=5)
        row += 1
        f.columnconfigure(1, weight=1)

        Label(f, text="iPhoto Library:").grid(sticky=E)
        iphoto_library_entry = Entry(f, textvariable=self.iphoto_library)
        iphoto_library_entry.grid(row=0, column=1, sticky=E+W)
        self.browse_library_button = Button(f, text="Browse...",
                                            command=self.browse_library)
        self.browse_library_button.grid(row=0, column=2)

        self.library_status = Label(f, textvariable=self.iphoto_library_status)
        self.library_status.grid(row=1, column=1, sticky=W)

        (cf, lf) = self._add_section(library_tab, "Events, Albums and Smart Albums",
                                     self.help_events)
        cf.grid(row=row, columnspan=2, stick=E+W)
        row += 1
        lf.columnconfigure(1, weight=1)
        Label(lf, text="Events:").grid(sticky=E)
        events_entry = Entry(lf, textvariable=self.events)
        events_entry.grid(row=0, column=1, sticky=EW)

        Label(lf, text="Albums:").grid(sticky=E)
        albums_entry = Entry(lf, textvariable=self.albums)
        albums_entry.grid(row=1, column=1, sticky=EW)

        Label(lf, text="Smart Albums:").grid(sticky=E)
        smarts_entry = Entry(lf, textvariable=self.smarts)
        smarts_entry.grid(row=2, column=1, columnspan=3, sticky=EW)

    def _create_files_tab(self, files_tab):
        files_tab.columnconfigure(0, weight=1)
        # Export folder and options
        row = 0
        (cf, lf) = self._add_section(files_tab, "Export Folder and Options", self.help_export)
        cf.grid(row=row, columnspan=2, stick=E+W)
        row += 1
        lf.columnconfigure(1, weight=1)
        label = Label(lf, text="Export Folder:")
        label.grid(sticky=E)
        export_folder_entry = Entry(lf, textvariable=self.export_folder)
        export_folder_entry.grid(row=0, column=1, columnspan=2, sticky=E+W)
        Button(lf, text="Browse...",
               command=self.browse_export).grid(row=0, column=3)

        update_box = Checkbutton(lf, text="Overwrite changed pictures",
                                 var=self.update_var)
        update_box.grid(row=1, column=1, sticky=W)
        originals_box = Checkbutton(lf, text="Export originals",
                                    var=self.originals_var)
        originals_box.grid(row=2, column=1, sticky=W)
        hint_box = Checkbutton(lf, text="Use folder hints",
                               var=self.folder_hints_var)
        hint_box.grid(row=3, column=1, sticky=W)

        delete_box = Checkbutton(lf, text="Delete obsolete pictures",
                                 var=self.delete_var)
        delete_box.grid(row=4, column=1, sticky=W)
        link_box = Checkbutton(lf, text="Use file links", var=self.link_var)
        link_box.grid(row=5, column=1, sticky=W)

        # Templates ----------------------------------------
        (cf, lf) = self._add_section(files_tab, "Name Templates", self.help_templates)
        cf.grid(row=row, columnspan=2, stick=E+W)
        row += 1
        lf.columnconfigure(1, weight=1)
        Label(lf, text="Folder names:").grid(sticky=E)
        foldertemplate_entry = Entry(lf, textvariable=self.foldertemplate)
        foldertemplate_entry.grid(row=0, column=1, sticky=EW)

        Label(lf, text="File names:").grid(sticky=E)
        nametemplate_entry = Entry(lf, textvariable=self.nametemplate)
        nametemplate_entry.grid(row=1, column=1, sticky=EW)

        Label(lf, text="Captions:").grid(sticky=E)
        captiontemplate_entry = Entry(lf, textvariable=self.captiontemplate)
        captiontemplate_entry.grid(row=2, column=1, sticky=EW)

    def _create_metadata_tab(self, metadata_tab):
        metadata_tab.columnconfigure(0, weight=1)
        row = 0
        # Metadata --------------------------------------------
        (cf, lf) = self._add_section(metadata_tab, "Metadata", self.help_metadata)
        cf.grid(row=row, columnspan=2, stick=E+W)
        row += 1
        self.iptc_box = Checkbutton(lf,
                                    text=("Export metadata (descriptions, "
                                          "keywords, ratings, dates)"),
                                    var=self.iptc_var, state=DISABLED,
                                    command=self.change_iptc_box)
        self.iptc_box.grid(row=0, column=0, columnspan=2, sticky=W)

        self.iptc_all_box = Checkbutton(lf,
                                        text="Check previously exported images",
                                        var=self.iptc_all_var,
                                        command=self.change_metadata_box,
                                        state=DISABLED)
        self.iptc_all_box.grid(row=1, column=0, sticky=W)

        self.gps_box = Checkbutton(lf,
                                   text="Export GPS data",
                                   var=self.gps_var,
                                   command=self.change_metadata_box,
                                   state=DISABLED)
        self.gps_box.grid(row=2, column=0, sticky=W)

        # Faces ---------------------------------------------------
        (cf, lf) = self._add_section(metadata_tab, "Faces", self.help_faces)
        cf.grid(row=row, columnspan=2, stick=E+W)
        row += 1
        lf.columnconfigure(2, weight=1)
        self.faces_box = Checkbutton(lf, text="Copy faces into metadata",
                                     var=self.faces_var, state=DISABLED,
                                     command=self.change_metadata_box)
        self.faces_box.grid(row=0, column=0, sticky=W)

        self.face_keywords_box = Checkbutton(
            lf,
            text="Copy face names into keywords",
            var=self.face_keywords_var,
            command=self.change_metadata_box,
            state=DISABLED)
        self.face_keywords_box.grid(row=1, column=0, sticky=W)

        checkbutton = Checkbutton(lf, text="Export faces into folders",
                                  var=self.face_albums_var)
        checkbutton.grid(row=2, column=0, sticky=W)
        label = Label(lf, text="Faces folder prefix:")
        label.grid(row=2, column=1, sticky=E)
        entry = Entry(lf, textvariable=self.face_albums_text)
        entry.grid(row=2, column=2, sticky=E+W)

    def create_widgets(self):
        """Builds the UI."""
        self.columnconfigure(0, weight=1)
        n = Notebook(self)
        n.grid(row=0, sticky=E+W+N+S)

        library_tab = Frame(n)
        n.add(library_tab, text='Library')
        self._create_library_tab(library_tab)

        files_tab = Frame(n)
        n.add(files_tab, text='Files')
        self._create_files_tab(files_tab)

        metadata_tab = Frame(n)
        n.add(metadata_tab, text='Metadata')
        self._create_metadata_tab(metadata_tab)

        self._create_button_bar(self, 1)

        self.text = ScrolledText(self, borderwidth=4, relief=RIDGE, padx=4,
                                 pady=4)
        self.text.grid(row=2, column=0, sticky=E+W+N+S)
        self.rowconfigure(2, weight=1)

    def change_iptc_box(self):
        """Clears some options that depend on the metadata export option."""
        mode = self.iptc_var.get()
        if not mode:
            self.faces_var.set(0)
            self.face_keywords_var.set(0)
            self.iptc_all_var.set(0)
            self.gps_var.set(0)

    def change_metadata_box(self):
        """Sets connected options if an option that needs meta data is changed.
        """
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

    def help_templates(self):
        HelpDialog(self, """Folder, file, and image caption templates.

Templates are strings with place holders for values. The place holders have
the format "{name}". Everything else in the template will be copied. Examples:
  {title}
  {yyyy}/{mm}/{dd} {title} - generates "2010/12/31 My Birthday" if the date
      of the pictures is Dec 31, 2010, and the title is "My Birthday".
  {yyyy} Event: {event} - generates "2010 Event: Birthday" for an event with
      any date in 2010 and the name "Birthday".

Available place holders for folder names:
  {name} - name of the album or event.
  {hint} - folder hint (taken from line event or album description starting with
           @).
  {yyyy} - year of album or event date.
  {mm} - month of album or event date.
  {dd} - date of album or event date.

Available place holders for file names:
  {album} - name of album (or in the case of an event, the name of the event).
  {index} - number of image in album, starting at 1.
  {index0} - number of image in album, padded with 0s, so that all numbers have
             the same length.
  {event} - name of the event. In the case of an album, the name of the event
            to which the image belongs.
  {event_index} - number of image in the event, starting at 1. If the case of an
                  album, this number will be based on the event to which the
                  image belongs.
  {event_index0} - same as {event_index}, but padded with leading 0s so that all
                   values have the same length.
  {title} - image title.
  {yyyy} - year of image.
  {mm} - month of image (01 - 12).
  {dd} - day of image (01 - 31).

  If you are using {album}/{index}/{index0} place holders, the image will be
  named based on whatever album or event it is contained. That means an image
  in two albums will be exported with different names, even so the files are
  identical. If you want to use the same name for each image, regardless of
  which album it is in, use {event}, {event_index}, and {event_index0} instead.

Available place holders for captions:
  {title} - image title.
  {description} - image description.
  {title_description} - concatenated image title and description, separated by a
                        : if both are set.
  {yyyy} - year of image.
  {mm} - month of image (01 - 12).
  {dd} - day of image (01 - 31).
""")

    def help_buttons(self):
        HelpDialog(self, """Export modes.

Click on "Dry Run" to see what Phoshare would do without actually modifying any
files.

Click on "Export" to export your files using the current settings.

All your settings will be saved when you click either Dry Run and Export, and
re-loaded if you restart Phoshare.

Check "Show debug output" to generate additional output message that can assist
in debugging Phoshare problems.
""")

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

Check previously exported images: If not checked, metadata will only be set for new or
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
        output in Phoshare.py."""

        def __init__(self):
            self.iphoto = '~/Pictures/iPhoto Library'
            self.export = '~/Pictures/Album'
            self.albums = ''
            self.events = '.'
            self.smarts = ''
            self.ignore = []
            self.delete = False
            self.update = False
            self.link = False
            self.dryrun = False
            self.folderhints = False
            self.captiontemplate = u'{description}'
            self.foldertemplate = u'{name}'
            self.nametemplate = u'{title}'
            self.aperture = False # TODO
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
            self.verbose = False

        def load(self):
            """Attempts to load saved options. Returns True if saved options
            were available."""
            if not os.path.exists(_CONFIG_PATH):
                return False
            config = ConfigParser.SafeConfigParser()
            config.read(_CONFIG_PATH)
            s = 'Export1'
            if config.has_option(s, 'iphoto'):
                self.iphoto = config.get(s, 'iphoto')
            if config.has_option(s, 'export'):
                self.export = config.get(s, 'export')
            if config.has_option(s, 'albums'):
                self.albums = config.get(s, 'albums')
            if config.has_option(s, 'events'):
                self.events = config.get(s, 'events')
            if config.has_option(s, 'smarts'):
                self.smarts = config.get(s, 'smarts')
            if config.has_option(s, 'foldertemplate'):
                self.foldertemplate = config.get(s, 'foldertemplate')
            if config.has_option(s, 'nametemplate'):
                self.nametemplate = config.get(s, 'nametemplate')
            if config.has_option(s, 'captiontemplate'):
                self.captiontemplate = config.get(s, 'captiontemplate')
            if config.has_option(s, 'delete'):
                self.delete = config.getboolean(s, 'delete')
            if config.has_option(s, 'update'):
                self.update = config.getboolean(s, 'update')
            if config.has_option(s, 'link'):
                self.link = config.getboolean(s, 'link')
            if config.has_option(s, 'folderhints'):
                self.folderhints = config.getboolean(s, 'folderhints')
            if config.has_option(s, 'captiontemplate'):
                self.nametemplate = unicode(config.get(s, 'captiontemplate'))
            if config.has_option(s, 'nametemplate'):
                self.nametemplate = unicode(config.get(s, 'nametemplate'))
            if config.has_option(s, 'size'):
                self.size = config.get(s, 'size')
            if config.has_option(s, 'picasa'):
                self.picasa = config.getboolean(s, 'picasa')
            if config.has_option(s, 'movies'):
                self.movies = config.getboolean(s, 'movies')
            if config.has_option(s, 'originals'):
                self.originals = config.getboolean(s, 'originals')
            if config.has_option(s, 'iptc'):
                self.iptc = config.getint(s, 'iptc')
            if config.has_option(s, 'gps'):
                self.gps = config.getboolean(s, 'gps')
            if config.has_option(s, 'faces'):
                self.faces = config.getboolean(s, 'faces')
            if config.has_option(s, 'facealbums'):
                self.facealbums = config.getboolean(s, 'facealbums')
            if config.has_option(s, 'facealbum_prefix'):
                self.facealbum_prefix = config.get(s, 'facealbum_prefix')
            if config.has_option(s, 'face_keywords'):
                self.face_keywords = config.getboolean(s, 'face_keywords')
            return True

        def save(self):
            """Saves the current options into a file."""
            config = ConfigParser.RawConfigParser()
            s = 'Export1'
            config.add_section(s)
            config.set(s, 'iphoto', self.iphoto)
            config.set(s, 'export', self.export)
            config.set(s, 'albums', su.fsenc(self.albums))
            config.set(s, 'events', su.fsenc(self.events))
            config.set(s, 'smarts', su.fsenc(self.smarts))
            config.set(s, 'foldertemplate', su.fsenc(self.foldertemplate))
            config.set(s, 'nametemplate', su.fsenc(self.nametemplate))
            config.set(s, 'captiontemplate', su.fsenc(self.captiontemplate))
            config.set(s, 'delete', self.delete)
            config.set(s, 'update', self.update)
            config.set(s, 'link', self.link)
            config.set(s, 'dryrun', self.dryrun)
            config.set(s, 'folderhints', self.folderhints)
            config.set(s, 'captiontemplate', self.captiontemplate)
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
            args = ['Phoshare.py', '--export', '"' + export_folder + '"']

            options = self.Options()
            options.iphoto = self.iphoto_library.get()
            args.extend(['--iphoto', '"' + options.iphoto + '"'])
            options.export = self.export_folder.get()
            options.dryrun = mode == "dry_run"
            options.albums = self.albums.get()
            if options.albums:
                args.extend(['--albums', '"' + options.albums + '"'])
            options.events = self.events.get()
            if options.events:
                args.extend(['--events', '"' + options.events + '"'])
            options.smarts = self.smarts.get()
            if options.smarts:
                args.extend(['--smarts', '"' + options.smarts + '"'])
            options.foldertemplate = unicode(self.foldertemplate.get())
            if options.foldertemplate:
                args.extend(['--foldertemplate', '"' +
                             options.foldertemplate + '"'])
            options.nametemplate = unicode(self.nametemplate.get())
            if options.nametemplate:
                args.extend(['--nametemplate', '"' +
                             options.nametemplate + '"'])
            options.captiontemplate = unicode(self.captiontemplate.get())
            if options.captiontemplate:
                args.extend(['--captiontemplate', '"' +
                             options.captiontemplate + '"'])
            options.ignore = []  # TODO
            options.update = self.update_var.get() == 1
            if options.update:
                args.append('--update')
            options.delete = self.delete_var.get() == 1
            if options.delete:
                args.append('--delete')
            options.originals = self.originals_var.get() == 1
            if options.originals:
                args.append('--originals')
            options.link = self.link_var.get() == 1
            if options.link:
                args.append('--link')
            options.folderhints = self.folder_hints_var.get() == 1
            if options.folderhints:
                args.append('--folderhints')
            options.faces = self.faces_var.get() == 1
            if options.faces:
                args.append('--faces')
            options.face_keywords = self.face_keywords_var.get() == 1
            if options.face_keywords:
                args.append('--face_keywords')
            if self.iptc_all_var.get() == 1:
                options.iptc = 2
                args.append('--iptcall')
            elif self.iptc_var.get() == 1:
                options.iptc = 1
                args.append('--iptc')
            else:
                options.iptc = 0
            options.gps = self.gps_var.get()
            if options.gps:
                args.append('--gps')
            options.facealbums = self.face_albums_var.get() == 1
            if options.facealbums:
                args.append('--facealbums')
            options.facealbum_prefix = self.face_albums_text.get()
            if options.facealbum_prefix:
                args.append('--facealbum_prefix')

            exclude = None # TODO

            options.save()
            print " ".join(args)

            self.logging_handler.setLevel(logging.DEBUG if self.verbose_var.get() else logging.INFO)
            self.active_library = phoshare_main.ExportLibrary(export_folder)
            phoshare_main.export_iphoto(self.active_library, data, exclude,
                                        options)
            self.thread_queue.put(("done", (True, mode, '')))
        except Exception, e:  # IGNORE:W0703
            self.thread_queue.put(("done",
                                   (False, mode,
                                    str(e) + '\n\n' + traceback.format_exc())))

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
        self.thread_queue.put(("write", text))

    def writelines(self, lines):  # lines already have '\n'
        """Writes text to the progress area of the UI. Uses the thread queue,
        and can be called from a non-UI thread."""
        for line in lines:
            self.write(line)


def main():
    """Main routine for phoshare_ui. Typically launched from Phoshare.py"""
    app = ExportApp()
    app.master.title(phoshare_version.PHOSHARE_VERSION)
    sys.stdout = app
    try:
        app.init()
        app.mainloop()
    except Exception, e:
        f = cStringIO.StringIO()
        traceback.print_exc(file=f)
        app.write_progress('--- Fatal Error ---\n')
        app.write_progress('Please include the information below in your bug'
                           ' report.\n\n')
        app.write_progress('%s\n\n%s\n' % (str(e), f.getvalue()))
        app.write_progress('\n'.join(os.uname()))
        app.write_progress('\nMac version: %s\n' % (platform.mac_ver()[0]))
        app.write_progress('Python version: %s\n' % (platform.python_version()))
        tkMessageBox.showerror(
            'Phoshare Error',
            'Phoshare encountered a serious problem and will shut down. '
            'Please copy the information shown in the application output panel '
            'when reporting this problem at\n'
            'http://code.google.com/p/phoshare/issues/entry\n\n%s.' % (str(e)))
        raise e

if __name__ == "__main__":
    main()
