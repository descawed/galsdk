import tkinter as tk
import tkinter.messagebox as tkmsg
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from galsdk.project import Project
from galsdk.manifest import Manifest, ManifestFile
from galsdk.tim import TimFormat
from galsdk.ui.image import ImageViewerTab
from galsdk.ui.tim_import import TimImportDialog
from psx.tim import Tim


class ArtTab(ImageViewerTab):
    """Editor tab for viewing general game art"""

    images: dict[str, tuple[ManifestFile, Tim, Manifest]]
    manifests: dict[str, Manifest]

    def __init__(self, project: Project):
        super().__init__('Art', project, supports_import=True, supports_insert=True)
        self.images = {}
        self.images_changed = set()
        self.manifests = {}
        self.manifests_changed = set()

        for art_manifest in self.project.get_art_manifests():
            self.tree.insert('', tk.END, text=art_manifest.name, iid=art_manifest.name, open=False)
            self.add_level(art_manifest, art_manifest.name)

    def add_level(self, manifest: Manifest, base_iid: str):
        self.manifests[base_iid] = manifest
        for art_file in manifest:
            new_iid = f'{base_iid}/{art_file.name}'

            if art_file.is_manifest:
                sub_manifest = Manifest.load_from(art_file.path)
                self.tree.insert(base_iid, tk.END, text=art_file.ext_name, iid=new_iid, open=False)
                self.add_level(sub_manifest, new_iid)
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

    def do_insert(self, path: Path, parent_iid: str, index: int):
        if path.suffix.lower() == '.tim':
            try:
                with path.open('rb') as f:
                    new_tim = Tim.read(f)
            except (ValueError, NotImplementedError) as e:
                tkmsg.showerror('Insert failed', str(e), parent=self)
                return
        else:
            try:
                image = Image.open(path)
                dialog = TimImportDialog(self.winfo_toplevel(), image)
                new_tim = dialog.output_tim
                if new_tim is None:
                    return
            except (ValueError, NotImplementedError, UnidentifiedImageError) as e:
                tkmsg.showerror('Insert failed', str(e), parent=self)
                return

        new_tim = TimFormat.from_tim(new_tim)
        manifest = self.manifests[parent_iid]
        name = manifest.get_unique_name(path.stem)
        mf = manifest.add_raw(new_tim.to_bytes(), index, name, new_tim.suggested_extension)
        iid = f'{parent_iid}/{name}'
        self.tree.insert(parent_iid, index, iid, text=f'* {mf.ext_name}')
        self.images[iid] = (mf, new_tim, manifest)
        self.images_changed.add(iid)
        self.manifests_changed.add(manifest)

    def do_delete(self, iid: str):
        mf, _, manifest = self.images[iid]
        del manifest[mf.name]
        del self.images[iid]
        self.context_ids.remove(iid)
        self.manifests_changed.add(manifest)
        self.notify_change()

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
            self.images[iid] = (mf, new_tim, manifest)
        else:
            try:
                tim.update_image_in_place(Image.open(path))
            except (ValueError, NotImplementedError, UnidentifiedImageError) as e:
                tkmsg.showerror('Import failed', str(e), parent=self)
                return

        self.images_changed.add(iid)
        self.tree.item(iid, text=f'* {mf.ext_name}')
        self.notify_change()

    @property
    def has_unsaved_changes(self) -> bool:
        return len(self.images_changed) > 0

    def save(self):
        for iid in self.images_changed:
            mf, tim, _ = self.images[iid]
            with mf.path.open('wb') as f:
                tim.write(f)
            self.tree.item(iid, text=mf.path.name)  # remove change marker
        for manifest in self.manifests_changed:
            manifest.save()
        self.images_changed.clear()
        self.manifests_changed.clear()
