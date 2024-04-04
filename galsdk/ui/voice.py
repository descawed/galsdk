import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase

from galsdk.ui.media import MediaPlayer
from galsdk.ui.tab import Tab
from galsdk.project import Project


class VoiceTab(Tab):
    """Tab for playing XA voice audio"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Voice', project)
        self.base = base
        self.audio = []
        self.current_index = None

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for audio in self.project.get_voice_audio():
            audio_id = len(self.audio)
            self.audio.append(audio)
            self.tree.insert('', tk.END, text=str(audio_id), iid=str(audio_id))

        self.player = MediaPlayer(self.base, 'voice', 0, 0, self, use_video=False)

        self.tree.grid(row=0, column=0, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.player.grid(row=0, column=2, sticky=tk.EW)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_audio)

    def select_audio(self, _):
        try:
            index = int(self.tree.selection()[0])
        except ValueError:
            return

        if index != self.current_index:
            self.current_index = index
            media = self.audio[index]
            audio = self.base.loader.loadSfx(media.playable_panda_path)
            self.player.set_media(audio, stats=media.stats)

    def set_active(self, is_active: bool):
        self.player.set_active(is_active)

    def close(self):
        self.player.close()

    @property
    def should_appear(self) -> bool:
        return not self.project.version.is_demo
