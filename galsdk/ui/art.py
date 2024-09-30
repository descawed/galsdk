import tkinter as tk
import tkinter.filedialog as tkfile
import tkinter.messagebox as tkmsg
import tkinter.simpledialog as tksimple
from pathlib import Path
from tkinter import ttk

from PIL import Image, UnidentifiedImageError

from galsdk.project import Project
from galsdk.manifest import Manifest, ManifestFile
from galsdk.tim import TimDb, TimFormat
from galsdk.ui.image import ImageViewerTab
from galsdk.ui.tim_import import TimImportDialog
from psx.tim import Tim


class InsertDialog(tksimple.Dialog):
    OPTIONS = {
        'TIM DB': 'tdb',
        'Compressed TIM DB': 'tdc',
        'TIM stream': 'tmm',
        'TIM': 'tim',
        'Single compressed TIM': 'tmc1',
        'Compressed TIM stream': 'tmc',
    }

    def __init__(self, parent: tk.BaseWidget):
        # redefined here because PyCharm can't see it on the base class for some reason
        self.result = None
        self.name_var = tk.StringVar()
        self.type_var = tk.StringVar(value='TIM DB')
        super().__init__(parent, 'Choose object to insert')

    def body(self, master: tk.BaseWidget):
        label = ttk.Label(master, text='Type:')
        label.grid(row=0, column=0, sticky=tk.W)
        select = ttk.Combobox(master, values=list(self.OPTIONS), textvariable=self.type_var, state='readonly')
        select.grid(row=0, column=1, sticky=tk.E)

        name_label = ttk.Label(master, text='Name:')
        name_label.grid(row=1, column=0, sticky=tk.W)
        name_entry = ttk.Entry(master, textvariable=self.name_var)
        name_entry.grid(row=1, column=1, sticky=tk.E)
        return name_entry

    def validate(self) -> bool:
        return len(self.name_var.get()) > 0

    def apply(self):
        self.result = (self.OPTIONS[self.type_var.get()], self.name_var.get())


class ArtTab(ImageViewerTab):
    """Editor tab for viewing general game art"""

    images: dict[str, tuple[ManifestFile, Tim, Manifest]]
    manifests: dict[str, Manifest]

    def __init__(self, project: Project):
        super().__init__('Art', project)
        self.images = {}
        self.images_changed = set()
        self.manifests = {}
        self.manifests_changed = set()

        for art_manifest in self.project.get_art_manifests():
            self.tree.insert('', tk.END, text=art_manifest.name, iid=art_manifest.name, open=False)
            self.add_level(art_manifest, art_manifest.name, False)

    def add_level(self, manifest: Manifest, base_iid: str, allow_context: bool = True):
        self.manifests[base_iid] = manifest
        if allow_context:
            self.context_ids.add(base_iid)
        for art_file in manifest:
            new_iid = f'{base_iid}/{art_file.name}'

            if art_file.is_manifest:
                self.tree.insert(base_iid, tk.END, text=art_file.ext_name, iid=new_iid, open=False)
                self.add_level(art_file.manifest, new_iid)
                continue

            if art_file.path.suffix.lower() != '.tim':
                # ignore files that aren't images
                continue

            self.tree.insert(base_iid, tk.END, text=art_file.ext_name, iid=new_iid)
            with art_file.path.open('rb') as f:
                self.images[new_iid] = (art_file, Tim.read(f), manifest)
            self.context_ids.add(new_iid)

    def get_image_from_iid(self, iid: str) -> Tim | None:
        # for some reason, PyCharm thinks that every index in this tuple is a ManifestFile
        # noinspection PyTypeChecker
        while iid not in self.images:
            children = self.tree.get_children(iid)
            if not children:
                return None
            iid = children[0]
        return self.images.get(iid, (None, None))[1]

    def configure_context_menu(self):
        self.context_menu.delete(0, tk.END)
        if self.context_iid in self.images:
            self.context_menu.add_command(label='Import', command=self.on_import)
            self.context_menu.add_command(label='Export', command=self.on_export)
            self.context_menu.add_separator()
        self.context_menu.add_command(label='Rename', command=self.on_rename)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Insert before', command=self.on_insert_before)
        self.context_menu.add_command(label='Insert after', command=self.on_insert_after)
        self.context_menu.add_command(label='Delete', command=self.on_delete)

    def get_context_index(self) -> tuple[str, int]:
        parent_iid = self.tree.parent(self.context_iid)
        index = self.tree.index(self.context_iid)
        return parent_iid, index

    def show_tim_import_dialog(self, path: Path, reference: Tim | None = None) -> Tim | None:
        image = Image.open(path)
        dialog = TimImportDialog(self.winfo_toplevel(), image, reference_tim=reference)
        return dialog.output_tim

    def ask_insert_tim(self) -> tuple[Path, TimFormat] | None:
        extensions = ['*.png', '*.jpg', '*.bmp', '*.tga', '*.webp', '*.tim']
        if filename := tkfile.askopenfilename(filetypes=[('Images', ' '.join(extensions)), ('All Files', '*.*')]):
            path = Path(filename)
            if path.suffix.lower() == '.tim':
                try:
                    with path.open('rb') as f:
                        new_tim = Tim.read(f)
                except (ValueError, NotImplementedError) as e:
                    tkmsg.showerror('TIM load failed', str(e), parent=self)
                    return None
            else:
                try:
                    new_tim = self.show_tim_import_dialog(path)
                    if new_tim is None:
                        return None
                except (ValueError, NotImplementedError, UnidentifiedImageError) as e:
                    tkmsg.showerror('TIM import failed', str(e), parent=self)
                    return None

            return path, TimFormat.from_tim(new_tim)
        else:
            return None

    def on_rename(self, *_):
        index = self.tree.index(self.context_iid)
        parent_iid = self.context_iid.rsplit('/', 1)[0]
        manifest = self.manifests[parent_iid]
        mf = manifest[index]
        new_name = tksimple.askstring('Rename', 'New name:', initialvalue=mf.name, parent=self)
        if new_name is None:
            return

        try:
            mf = manifest.rename(index, new_name)
        except KeyError as e:
            tkmsg.showerror('Rename failed', str(e), parent=self)
            return
        self.tree.item(self.context_iid, text=f'* {mf.ext_name}')
        if self.context_iid in self.manifests:
            self.manifests_changed.add(self.context_iid)
        self.manifests_changed.add(parent_iid)
        self.notify_change()

    def on_insert(self, parent_iid: str, index: int):
        allow_flatten = False
        name = None
        if self.context_iid in self.images:
            ext = 'tim'
        else:
            dialog = InsertDialog(self)
            result = dialog.result
            if result is None:
                return

            ext, name = result
            if ext == 'tmc1':
                ext = 'tmc'
                allow_flatten = True

        result = self.ask_insert_tim()
        if result is None:
            return

        path, tim = result
        manifest = self.manifests[parent_iid]
        if name is None:
            name = path.stem
        name = manifest.get_unique_name(name, True)

        if ext != 'tim':
            # create database
            db = TimDb(TimDb.Format.from_extension(ext), allow_flatten=allow_flatten)
            db.append(tim)
            new_manifest_path = manifest.path / name
            new_manifest = Manifest.from_archive(new_manifest_path, name, db, 'TIM')
            mf = manifest.add_manifest(new_manifest, index, name, db.suggested_extension, db.should_flatten)
            self.manifests_changed.add(parent_iid)
        else:
            new_manifest = None
            mf = manifest.add_raw(tim.to_bytes(), index, name, tim.suggested_extension)

        iid = f'{parent_iid}/{name}'
        if mf.is_manifest:
            self.tree.insert(parent_iid, index, iid, text=f'* {mf.ext_name}')
            self.manifests[iid] = new_manifest
            self.context_ids.add(iid)
            parent_iid = iid
            mf = new_manifest[0]
            iid = f'{parent_iid}/{name}'
            manifest = new_manifest
        self.tree.insert(parent_iid, index, iid, text=f'* {mf.ext_name}')
        self.images[iid] = (mf, tim, manifest)
        self.images_changed.add(iid)
        self.manifests_changed.add(parent_iid)
        self.context_ids.add(iid)
        self.notify_change()

        self.tree.see(iid)
        self.tree.selection_set(iid)

    def on_insert_before(self, *_):
        parent_iid, index = self.get_context_index()
        self.on_insert(parent_iid, index)

    def on_insert_after(self, *_):
        parent_iid, index = self.get_context_index()
        self.on_insert(parent_iid, index + 1)

    def on_delete(self, *_):
        name = self.tree.item(self.context_iid, 'text')
        if name.startswith('* '):
            name = name[2:]
        if not tkmsg.askyesno('Confirm', f'Are you sure you want to delete {name}?', icon=tkmsg.WARNING,
                              parent=self):
            return
        parent_iid, index = self.get_context_index()
        manifest = self.manifests[parent_iid]
        del manifest[index]
        if self.context_iid in self.images:
            del self.images[self.context_iid]
            if self.context_iid in self.images_changed:
                self.images_changed.remove(self.context_iid)
        if self.context_iid in self.manifests:
            del self.manifests[self.context_iid]
            if self.context_iid in self.manifests_changed:
                self.manifests_changed.remove(self.context_iid)
        self.tree.delete(self.context_iid)
        self.context_ids.remove(self.context_iid)
        self.manifests_changed.add(parent_iid)
        self.notify_change()

    def on_import(self, *_):
        if self.context_iid not in self.images:
            return

        extensions = ['*.png', '*.jpg', '*.bmp', '*.tga', '*.webp', '*.tim']
        if filename := tkfile.askopenfilename(filetypes=[('Images', ' '.join(extensions)), ('All Files', '*.*')]):
            self.do_import(Path(filename), self.context_iid)
            self.image_view.image = self.get_image()

    def do_import(self, path: Path, iid: str):
        mf, tim, manifest = self.images[iid]
        if path.suffix.lower() == '.tim':
            try:
                with path.open('rb') as f:
                    new_tim = Tim.read(f)
            except (ValueError, NotImplementedError) as e:
                tkmsg.showerror('Import failed', str(e), parent=self)
                return
            if not tim.is_compatible_with(new_tim):
                confirm = tkmsg.askyesno('Incompatible TIMs', 'This TIM does not have the same attributes '
                                         'as the original TIM. The game may not be able to load it. Are you sure you '
                                         'want to continue?', parent=self)
                if not confirm:
                    return
        else:
            try:
                new_tim = self.show_tim_import_dialog(path, tim)
                if new_tim is None:
                    return  # user cancelled
            except (ValueError, NotImplementedError, UnidentifiedImageError) as e:
                tkmsg.showerror('Import failed', str(e), parent=self)
                return

        self.images[iid] = (mf, new_tim, manifest)
        self.images_changed.add(iid)
        self.tree.item(iid, text=f'* {mf.ext_name}')
        self.notify_change()

    @property
    def has_unsaved_changes(self) -> bool:
        return len(self.images_changed) > 0 or len(self.manifests_changed) > 0

    def save(self):
        for iid in self.images_changed:
            # check if the image was deleted after it was changed
            if iid not in self.images:
                continue
            if not self.tree.exists(iid):
                del self.images[iid]
                continue

            mf, tim, _ = self.images[iid]
            with mf.path.open('wb') as f:
                tim.write(f)
            self.tree.item(iid, text=mf.ext_name)  # remove change marker
        for iid in self.manifests_changed:
            # check if the manifest was deleted after it was changed
            if iid not in self.manifests:
                continue
            if not self.tree.exists(iid):
                del self.manifests[iid]
                continue

            manifest = self.manifests[iid]
            manifest.save()
            old_text = self.tree.item(iid, 'text')
            if old_text.startswith('* '):
                self.tree.item(iid, text=old_text[2:])
        self.images_changed.clear()
        self.manifests_changed.clear()
