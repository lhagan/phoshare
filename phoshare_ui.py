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
import phoshare

from ScrolledText import ScrolledText

import Queue


class ExportApp(Frame):

    def __init__(self, options, master=None):
        """Initialize the app, setting up the UI."""
        Frame.__init__(self, master, bd=10)

        self.thread_queue = Queue.Queue(maxsize=100)
        self.export_running = None
        
        top = self.winfo_toplevel()
        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)
        self.grid(sticky=N+S+E+W)

        self.valid_library = False

        self.iphoto_library = StringVar()
        self.iphoto_library_status = StringVar()
        self.browse_library_button = None
        self.export_folder = StringVar()

        self.library_status = None
        self.dryrun_button = None
        self.export_button = None
        self.text = None

        self.events = StringVar()
        if options.events:
            self.events.set(options.events)
        else:
            self.events.set(".")
        self.albums = StringVar()
        if options.albums:
            self.albums.set(options.albums)
        self.smarts = StringVar()
        if options.smarts:
            self.smarts.set(options.smarts)

        self.update_var = IntVar()
        if options.update:
            self.update_var.set(1)
        self.delete_var = IntVar()
        if options.delete:
            self.delete_var.set(1)
        self.originals_var = IntVar()
        if options.originals:
            self.originals_var.set(1)
        self.link_var = IntVar()
        if options.link:
            self.link_var.set(1)
        self.folder_hints_var = IntVar()
        if options.folderhints:
            self.folder_hints_var.set(1)
        self.faces_var = IntVar()
        if options.faces:
            self.faces_var.set(1)
        self.face_keywords_var = IntVar()
        if options.face_keywords:
            self.face_keywords_var.set(1)
        self.face_albums_var = IntVar()
        self.face_albums_text = StringVar()
        if options.facealbums:
            self.face_albums_var.set(1)
            self.face_albums_text.set(options.facealbums)

        self.create_widgets()

        if options.iphoto:
            self.iphoto_library.set(options.iphoto)
        else:
            self.iphoto_library.set("~/Pictures/iPhoto Library")
        if options.export:
            self.export_folder.set(options.export)
        else:
            self.export_folder.set("~/Pictures/Album")

        # More defaults to load:
        # self.nametemplate = "${caption}"
        # self.size = None  # TODO
        # self.picasa = False  # TODO
        # self.movies = True  # TODO
        # self.iptc = 0  # TODO
        # self.gps = False  # TODO

    def init(self):
        self.threadChecker()                
        self.check_iphoto_library()

    def create_widgets(self):
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
        self.library_status = Label(self, textvariable=self.iphoto_library_status)
        self.library_status.grid(row=row, column=1, columnspan=2, sticky=W)

        row += 1
        label = Label(self, text="Events, Albums and Smart Albums")
        label.config(font=bold_font)
        label.grid(row=row, column=0, columnspan=4, sticky=W)

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

        row += 1
        label = Label(self, text="Export Folder:")
        label.grid(sticky=E)
        export_folder_entry = Entry(self, textvariable=self.export_folder)
        export_folder_entry.grid(row=row, column=1, columnspan=2, sticky=E+W)
        Button(self, text="Browse...", command=self.browse_export).grid(row=row, column=3)

        row += 1
        update_box = Checkbutton(self, text="Overwrite changed pictures", var=self.update_var)
        update_box.grid(row=row, column=1, sticky=W)
        originals_box = Checkbutton(self, text="Export originals", var=self.originals_var)
        originals_box.grid(row=row, column=2, sticky=W)
        hint_box = Checkbutton(self, text="Use folder hints", var=self.folder_hints_var)
        hint_box.grid(row=row, column=3, sticky=W)

        row += 1
        delete_box = Checkbutton(self, text="Delete obsolete pictures", var=self.delete_var)
        delete_box.grid(row=row, column=1, sticky=W)
        link_box = Checkbutton(self, text="Use file links", var=self.link_var)
        link_box.grid(row=row, column=2, columnspan=2, sticky=W)

        row += 1
        label = Label(self, text="Faces and places")
        label.config(font=bold_font)
        label.grid(row=row, column=0, columnspan=4, sticky=W)

        row += 1
        checkbutton = Checkbutton(self, text="Export faces into folders", var=self.face_albums_var)
        checkbutton.grid(row=row, column=1, sticky=W)
        label = Label(self, text="Faces folder prefix:")
        label.grid(row=row, column=2, sticky=E)
        entry = Entry(self, textvariable=self.face_albums_text)
        entry.grid(row=row, column=3, sticky=E+W)

        row += 1
        faces_box = Checkbutton(self, text="Copy faces into metadata", var=self.faces_var)
        faces_box.grid(row=row, column=1, sticky=W)
        
        face_keywords_box = Checkbutton(self, text="Copy face namess into keywords", var=self.face_keywords_var)
        face_keywords_box.grid(row=row, column=2, columnspan=2, sticky=W)

        row += 1
        label = Label(self, text="Metadata")
        label.config(font=bold_font)
        label.grid(row=row, column=0, columnspan=4, sticky=W)

        row += 1
        self.dryrun_button = Button(self, text="Dry Run", command=self.do_dryrun, state=DISABLED)
        self.dryrun_button.grid(row=row, column=2, stick=E)
        self.export_button = Button(self, text="Export", command=self.do_export, state=DISABLED)
        self.export_button.grid(row=row, column=3)

        row += 1
        self.text = ScrolledText(self)
        self.text.grid(row=row, column=0, columnspan=4, sticky=E+W+N+S)
        self.rowconfigure(row, weight=1)

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
        if self.export_running:
            self.stop_thread()
            return
        if not self.can_export():
            return
        self.export_button.config(text="Stop Export")
        self.dryrun_button.config(state=DISABLED)
        self.run_export(False)

    def do_dryrun(self):
        if self.export_running:
            self.stop_thread()
            return
        if not self.can_export():
            return
        self.dryrun_button.config(text="Stop Dry Run")
        self.export_button.config(state=DISABLED)
        self.run_export(True)

    def stop_thread(self):
        tkMessageBox.showerror(
            "Stop Export",
            "Sorry, it is currently not possible to interrupt an ongoing export operation.")
        
    def export_done(self):
        self.dryrun_button.config(text="Dry Run")
        self.export_button.config(text="Export")
        self.enable_buttons()

    class Options(object):
        """Simple helper to create an object compatible with the OptionParser output in
           phoshare.py."""

        def __init__(self):
            self.albums = None
            self.events = None
            self.smarts = None
            self.delete = False
            self.update = False
            self.link = False 
            self.dryrun = False
            self.folderhints = False
            self.nametemplate = "${caption}"
            self.size = None  # TODO
            self.picasa = False  # TODO
            self.movies = True  # TODO
            self.originals = False
            self.iptc = 0  # TODO
            self.gps = False  # TODO
            self.faces = False
            self.facealbums = None
            self.face_keywords = False

    def can_export(self):
        if not self.albums.get() and not self.events.get() and not self.smarts.get():
            tkMessageBox.showerror(
                "Export Error",
                "Need to specify at least one event, album, or smart album for exporting.")
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
        self.export_running = threading.Thread(target=self.export_thread,
                                               args=(mode,))
        self.export_running.start()

    def export_thread(self, mode):
        """Run an export operation in a thread, to not block the UI.

        Args:
            mode - name of operation to run, "library", "dry_run", or "export".
        """
        try:
            # First, load the iPhoto library.
            library_path = self.iphoto_library.get()
            if library_path.startswith("~"):
                library_path = os.environ.get('HOME') + library_path[1:]
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
            export_folder = self.export_folder.get()
            if export_folder.startswith("~"):
                export_folder = os.environ.get('HOME') + export_folder[1:]
            
            options = self.Options()
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
            if self.face_albums_var.get():
                options.facealbums = self.face_albums_text.get()
            
            exclude = None # TODO

            exclude_folders = []  # TODO
            phoshare.export_iphoto(data, export_folder, exclude, exclude_folders,
                                   options)
            self.thread_queue.put(("done", (True, mode, '')))
        except Exception, e:
            self.thread_queue.put(("done", (False, mode, str(e))))
            print >> sys.stderr, e
        
    def threadChecker(self, delayMsecs=100):        # 10x per second
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
                self.export_running = None
            except Queue.Empty:
                break

        # Check the queue again after a short delay.
        self.after(delayMsecs, self.threadChecker)

    def write(self, text):
        """Writes text to the progress area of the UI. Uses the thread queue,
        and can be called from a non-UI thread."""
        self.thread_queue.put(("write", str(text)))
        
    def writelines(self, lines):  # lines already have '\n'
        """Writes text to the progress area of the UI. Uses the thread queue,
        and can be called from a non-UI thread."""
        for line in lines:
            self.write(line)     


def main(args):
    """main routine for phoshare_ui."""
    (options, args) = phoshare.parseArgs()
    app = ExportApp(options)
    app.master.title("phoshare 2.0 Beta")
    sys.stdout = app
    app.init()
    app.mainloop()

if __name__ == "__main__":
    main(sys.argv[1:])
