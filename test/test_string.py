from galsdk.string import LatinStringDb


def test_read_write(tmp_path):
    test_path = tmp_path / 'string.db'
    strings = ['first string', 'second string', 'hello world']

    db = LatinStringDb()
    for string in strings:
        db.append(string)
    with test_path.open('wb') as f:
        db.write(f)

    with test_path.open('rb') as f:
        new_db = LatinStringDb.read(f)
    assert list(new_db) == strings
