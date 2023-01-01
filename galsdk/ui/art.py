import tkinter as tk
from typing import Optional

from galsdk.ui.image import ImageViewerTab
from galsdk.project import Project
from psx.tim import Tim


class ArtTab(ImageViewerTab):
    """Editor tab for viewing general game art"""

    images: dict[str, Tim]
    current_image: Optional[Tim]

    def __init__(self, project: Project):
        super().__init__('Art', project)
        self.images = {}
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
                    self.images[iid] = Tim.read(f)

    def get_image(self) -> Optional[Tim]:
        selected = self.tree.selection()[0]
        return self.images.get(selected)
