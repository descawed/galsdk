import tkinter as tk
import tkinter.filedialog as tkfile
import tkinter.messagebox as tkmsg
from pathlib import Path
from tkinter import ttk

from galsdk.project import Project


class ExportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, project: Project):
        super().__init__(parent)
        self.transient(parent)
        self.project = project
        default_export_path = str(project.default_export_image)
        self.base_var = tk.StringVar(self, default_export_path)
        self.output_var = tk.StringVar(self, default_export_path)
        self.date_var = tk.StringVar(self, 'base')
        self.date_var.trace_add('write', self.update_modifications)
        self.status_var = tk.StringVar(self)

        self.title('Export')
        
        base_label = ttk.Label(self, text='Base image:', anchor=tk.E)
        base_entry = ttk.Entry(self, textvariable=self.base_var)
        base_browse = ttk.Button(self, text='Browse...', command=self.ask_base_image)

        output_label = ttk.Label(self, text='Output image:', anchor=tk.E)
        output_entry = ttk.Entry(self, textvariable=self.output_var)
        output_browse = ttk.Button(self, text='Browse...', command=self.ask_output_image)

        date_select_frame = ttk.Labelframe(self, text='Select changes by')
        base_radio = ttk.Radiobutton(date_select_frame, text='Base image modified date', value='base',
                                     variable=self.date_var)
        create_radio = ttk.Radiobutton(date_select_frame, text='Project create date', value='create',
                                       variable=self.date_var)
        export_radio = ttk.Radiobutton(date_select_frame, text='Last export date', value='export',
                                       variable=self.date_var)

        input_frame = ttk.Labelframe(self, text='Project files')
        self.input_tree = ttk.Treeview(input_frame, selectmode='none', show='tree')
        input_scroll = ttk.Scrollbar(input_frame, command=self.input_tree.yview, orient='vertical')
        output_frame = ttk.Labelframe(self, text='Image files')
        self.output_tree = ttk.Treeview(output_frame, selectmode='none', show='tree')
        output_scroll = ttk.Scrollbar(output_frame, command=self.output_tree.yview, orient='vertical')

        self.export_button = ttk.Button(self, text='Export', command=self.export)
        status_label = ttk.Label(self, textvariable=self.status_var)

        base_label.grid(padx=5, pady=5, row=0, column=0, sticky=tk.NE)
        base_entry.grid(padx=5, pady=5, row=0, column=1, columnspan=2, sticky=tk.NE + tk.W)
        base_browse.grid(padx=5, pady=5, row=0, column=3, sticky=tk.N + tk.E)

        output_label.grid(padx=5, pady=5, row=1, column=0, sticky=tk.NE)
        output_entry.grid(padx=5, pady=5, row=1, column=1, columnspan=2, sticky=tk.NE + tk.W)
        output_browse.grid(padx=5, pady=5, row=1, column=3, sticky=tk.N + tk.E)

        date_select_frame.grid(padx=5, pady=5, row=2, column=0, rowspan=3, columnspan=4, sticky=tk.EW)
        base_radio.pack(fill=tk.X, anchor=tk.W)
        create_radio.pack(fill=tk.X, anchor=tk.W)
        export_radio.pack(fill=tk.X, anchor=tk.W)

        input_frame.grid(padx=5, pady=5, row=5, column=0, rowspan=3, columnspan=2, sticky=tk.NSEW)
        output_frame.grid(padx=5, pady=5, row=5, column=2, rowspan=3, columnspan=2, sticky=tk.NSEW)

        self.input_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        input_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        output_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.export_button.grid(padx=5, pady=5, row=8, column=0, sticky=tk.SW)
        status_label.grid(pady=3, row=8, column=1, columnspan=3, sticky=tk.SW)

        self.grid_rowconfigure(5, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        base_entry.bind('<FocusOut>', self.update_base)
        output_entry.bind('<FocusOut>', self.update_export_status)

        self.update_modifications()

    def update_base(self, *_):
        self.update_export_status()
        if self.date_var.get() == 'base':
            self.update_modifications()

    def ask_base_image(self, *_):
        image_path = tkfile.askopenfilename(filetypes=[('CD images', '*.bin *.img'), ('All files', '*.*')], parent=self)
        if image_path:
            self.base_var.set(image_path)
            self.update_base()

    def ask_output_image(self, *_):
        image_path = tkfile.askopenfilename(filetypes=[('CD images', '*.bin *.img'), ('All files', '*.*')], parent=self)
        if image_path:
            self.output_var.set(image_path)
            self.update_export_status()

    def update_export_status(self, *_):
        statuses = []
        base_path = Path(self.base_var.get())
        if not base_path.exists():
            statuses.append('Invalid base image path.')

        output_path = Path(self.output_var.get())
        if not output_path.parent.exists():
            statuses.append('Invalid output image directory.')

        if len(self.input_tree.get_children()) == 0:
            statuses.append('No modifications to export.')

        self.export_button.configure(state=tk.DISABLED if statuses else tk.NORMAL)
        self.status_var.set(' '.join(statuses))

    def get_modified_timestamp(self) -> float | None:
        date_select = self.date_var.get()
        if date_select == 'base':
            base_path = Path(self.base_var.get())
            if not base_path.exists():
                self.update_export_status()
                tkmsg.showerror('Invalid base image', f'Path {base_path} does not exist', parent=self)
                return None
            mtime = base_path.stat().st_mtime
        elif date_select == 'create':
            mtime = self.project.create_date.timestamp()
        else:
            mtime = self.project.last_export_date.timestamp()
        return mtime

    def update_modifications(self, *_):
        self.input_tree.delete(*self.input_tree.get_children())
        self.output_tree.delete(*self.output_tree.get_children())

        mtime = self.get_modified_timestamp()
        if mtime is None:
            return

        input_files, output_files = self.project.get_files_modified(mtime)

        input_files.sort()
        output_files.sort()
        for paths, tree in [(input_files, self.input_tree), (output_files, self.output_tree)]:
            for path in paths:
                prefix = ''
                for part in path.parts:
                    iid = prefix + part + '/'
                    if not tree.exists(iid):
                        tree.insert(prefix, tk.END, text=part, iid=iid)
                    prefix = iid

        self.update_export_status()

    def export(self, *_):
        mtime = self.get_modified_timestamp()
        if mtime is None:
            return

        base_path = Path(self.base_var.get())
        output_path = Path(self.output_var.get())
        try:
            self.project.export(base_path, output_path, mtime)
        except Exception as e:
            tkmsg.showerror('Failed to export project', str(e), parent=self)
        else:
            tkmsg.showinfo('Success', 'Export completed successfully', parent=self)
            self.destroy()
