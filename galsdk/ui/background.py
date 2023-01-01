import tkinter as tk
from pathlib import Path
from typing import Optional

from galsdk.ui.image import ImageViewerTab
from galsdk.project import Project, Stage
from galsdk.tim import TimDb
from psx.tim import Tim


class BackgroundTab(ImageViewerTab):
    """Editor tab for viewing room background images"""

    dbs: list[tuple[Path, Optional[TimDb]]]
    current_image: Optional[Tim]

    def __init__(self, project: Project):
        super().__init__('Background', project)
        self.dbs = []
        self.current_image = None

        for stage in Stage:
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            bg_manifest = self.project.get_stage_backgrounds(stage)
            for bg_db in bg_manifest:
                db_id = len(self.dbs)
                self.dbs.append((bg_db.path, None))
                bg_id = f'db_{db_id}'
                self.tree.insert(stage, tk.END, text=bg_db.name, iid=bg_id, open=False)
                # dummy item so we have the option to expand
                self.tree.insert(bg_id, tk.END, text='Dummy')

    def on_node_open(self, event: tk.Event):
        focused = self.tree.focus()
        if focused.startswith('db_'):
            index = int(focused[3:])
            db_path = self.dbs[index]
            if db_path[1] is None:
                with db_path[0].open('rb') as f:
                    db = TimDb.read(f, fmt=TimDb.Format.from_extension(db_path[0].suffix))
                self.dbs[index] = (db_path[0], db)
                db_id = f'db_{index}'
                self.tree.set_children(db_id)  # remove the dummy entry
                for i in range(len(db)):
                    self.tree.insert(db_id, tk.END, text=str(i), iid=f'img_{index}_{i}')

    def get_image(self) -> Optional[Tim]:
        selected = self.tree.selection()[0]
        if selected.startswith('img_'):
            db_index, img_index = [int(piece) for piece in selected[4:].split('_')]
            db = self.dbs[db_index][1]
            return db[img_index]
        return None
