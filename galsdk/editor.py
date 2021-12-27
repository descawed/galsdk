from direct.showbase.ShowBase import ShowBase

from galsdk.project import Project


class Editor(ShowBase):
    """Main editor window"""

    def __init__(self):
        super().__init__(self)
        self.project = Project()


app = Editor()
app.run()
