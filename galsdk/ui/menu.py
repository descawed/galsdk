import tkinter as tk
from typing import Optional

from PIL.Image import Image

from galsdk.ui.image import ImageViewerTab
from galsdk.project import Project
from psx.exe import Region
from psx.tim import Tim


class MenuTab(ImageViewerTab):
    """Editor for viewing menus (only present in Western versions)"""

    def __init__(self, project: Project):
        super().__init__('Menu', project)
        self.images = {}
        self.current_image = None

        for name, menu in self.project.get_menus():
            self.tree.insert('', tk.END, text=name, iid=name, open=False)
            try:
                self.images[name] = menu.render()
                self.exportable_ids.add(name)
            except NotImplementedError:
                pass

            for i, tile in enumerate(menu):
                iid = f'{name}_{i}'
                self.tree.insert(name, tk.END, text=f'{i}', iid=iid)
                self.images[iid] = tile
                self.exportable_ids.add(iid)

    def get_image_from_iid(self, iid: str) -> Optional[Image]:
        return self.images.get(iid)

    @property
    def should_appear(self) -> bool:
        return self.project.version.region != Region.NTSC_J
