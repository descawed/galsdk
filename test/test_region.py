import os.path

import pytest

from psx.cd.disc import Disc
from psx.cd.region import SystemArea, VolumeDescriptor, PathTable, Directory, Free, File


VOLUME_NAME = '01_05_2022'


@pytest.fixture
def sample_disc(request):
    path = os.path.join(os.path.dirname(request.module.__file__), 'test.bin')
    with open(path, 'rb') as f:
        yield Disc(f)


def test_system_area(sample_disc):
    system_area = SystemArea()
    regions = system_area.read(sample_disc)
    assert system_area in regions
    assert system_area.get_primary_volume() is not None


def test_volume(sample_disc):
    vd = VolumeDescriptor(16)
    regions = vd.read(sample_disc)
    assert vd in regions
    assert vd.name == VOLUME_NAME
    assert vd.is_filesystem
    assert vd.next_volume is not None


def test_path_table(sample_disc):
    path_table = PathTable(20, 'little')
    path_table.read(sample_disc)
    assert path_table.size == 1


def test_directory(sample_disc):
    d = Directory(28, name=f'{VOLUME_NAME}:\\')
    d.read(sample_disc)
    assert d.size == 1


def test_file(sample_disc):
    f = File(30, name=rf'{VOLUME_NAME}:\TEST.TXT', byte_len=11)
    f.read(sample_disc)
    assert f.size == 1
    assert f.data_size == 11
    assert f.data == b'hello world'


def test_free(sample_disc):
    free = Free(2, 6)
    free.read(sample_disc)
    assert free.size == 5


def test_patch(tmp_path, sample_disc):
    system_area = SystemArea()
    regions = system_area.read(sample_disc)
    test_data = b'this is the test data'
    for region in regions:
        if region.name == rf'{VOLUME_NAME}:\TEST.TXT':
            region.patch_data(test_data)
            system_area.update_paths(region)
            break
    else:
        raise FileNotFoundError('Test file not found')

    output = tmp_path / 'output.bin'
    # ensure regions are in disc order and fill free regions before writing them out
    regions.sort(key=lambda r: (r.start, r.end))
    with output.open('w+b') as f:
        output_disc = Disc(f)
        last_region = None
        for region in regions:
            if last_region and region.start - last_region.end > 1:
                free_region = Free(last_region.end + 1, region.start - 1)
                free_region.read(sample_disc)
                free_region.write(output_disc)
            region.write(output_disc)
            last_region = region
        output_system_area = SystemArea()
        output_regions = output_system_area.read(output_disc)
    for region in output_regions:
        if region.name == rf'{VOLUME_NAME}:\TEST.TXT':
            assert region.data_size == len(test_data)
            break
    else:
        raise FileNotFoundError('Output test file not found')

