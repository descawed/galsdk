import pytest

from psx.cd.disc import Disc, Sector


@pytest.fixture
def sample_bin(tmp_path):
    path = tmp_path / 'test.bin'
    with path.open('wb') as f:
        disc = Disc(f)
        disc.write_sector(Sector(minute=1, second=2, sector=3))
        disc.write_sector(Sector(minute=4, second=5, sector=6))
        disc.write_sector(Sector(minute=7, second=8, sector=9))
    return path


def test_read(sample_bin):
    with sample_bin.open('rb') as f:
        disc = Disc(f)
        sector = disc.read_sector()
        assert sector.minute == 1
        assert sector.second == 2
        assert sector.sector == 3


def test_read_multiple(sample_bin):
    with sample_bin.open('rb') as f:
        disc = Disc(f)
        sectors = disc.read_sectors(2)
        assert len(sectors) == 2
        assert sectors[0].minute == 1
        assert sectors[0].second == 2
        assert sectors[0].sector == 3
        assert sectors[1].minute == 4
        assert sectors[1].second == 5
        assert sectors[1].sector == 6


def test_seek(sample_bin):
    with sample_bin.open('rb') as f:
        disc = Disc(f)
        disc.seek(2)
        sector = disc.read_sector()
        assert sector.minute == 7
        assert sector.second == 8
        assert sector.sector == 9
        disc.seek(0)
        sector = disc.read_sector()
        assert sector.minute == 1
        assert sector.second == 2
        assert sector.sector == 3
