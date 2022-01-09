from galsdk.project import GameVersion, Project, Region


def test_save_open(tmp_path):
    project = Project(tmp_path, GameVersion(Region.NTSC_J, 'ja', 2))
    project.save()

    other_project = Project.open(str(tmp_path))
    assert project.version == other_project.version
    assert project.last_export_date == other_project.last_export_date
