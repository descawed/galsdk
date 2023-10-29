import tkinter as tk
import tkinter.messagebox as tkmsg
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from galsdk.project import Project
from galsdk.manifest import ManifestFile
from galsdk.ui.image import ImageViewerTab
from psx.tim import Tim


class ArtTab(ImageViewerTab):
    """Editor tab for viewing general game art"""

    images: dict[str, tuple[ManifestFile, Tim]]
    current_image: Tim | None

    def __init__(self, project: Project):
        super().__init__('Art', project, supports_import=True)
        self.images = {}
        self.images_changed = set()
        self.current_image = None

        paths_seen = set()
        for art_manifest in self.project.get_art_manifests():
            self.tree.insert('', tk.END, text=art_manifest.name, iid=art_manifest.name, open=False)
            for art_file in art_manifest.iter_flat():
                if art_file.path.suffix.lower() != '.tim':
                    # ignore files that aren't images
                    continue
                relative_path = art_file.path.relative_to(art_manifest.path)
                iid = art_manifest.name
                for part in relative_path.parts:
                    new_iid = f'{iid}/{part}'
                    if new_iid not in paths_seen:
                        self.tree.insert(iid, tk.END, text=part, iid=new_iid)
                        paths_seen.add(new_iid)
                    iid = new_iid
                with art_file.path.open('rb') as f:
                    self.images[iid] = (art_file, Tim.read(f))
                self.context_ids.add(iid)

    def get_image_from_iid(self, iid: str) -> Tim | None:
        # for some reason, PyCharm thinks that every index in this tuple is a ManifestFile
        # noinspection PyTypeChecker
        return self.images.get(iid, (None, None))[1]

    def do_import(self, path: Path, iid: str):
        mf, tim = self.images[iid]
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
            self.images[iid] = (mf, new_tim)
        else:
            try:
                tim.update_image_in_place(Image.open(path))
            except (ValueError, NotImplementedError, UnidentifiedImageError) as e:
                tkmsg.showerror('Import failed', str(e), parent=self)
                return

        self.images_changed.add(iid)
        self.tree.item(iid, text=f'* {mf.path.name}')
        self.notify_change()

    @property
    def has_unsaved_changes(self) -> bool:
        return len(self.images_changed) > 0

    def save(self):
        for iid in self.images_changed:
            mf, tim = self.images[iid]
            with mf.path.open('wb') as f:
                tim.write(f)
            self.tree.item(iid, text=mf.path.name)  # remove change marker
        self.images_changed.clear()
