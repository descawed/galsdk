from galsdk.string import StringDb


def test_read_write(tmp_path):
    test_path = tmp_path / 'string.db'
    strings = ['first string', 'second string', 'hello world']

    db = StringDb()
    for string in strings:
        db.append(string)
    with test_path.open('wb') as f:
        db.write(f)

    new_db = StringDb()
    with test_path.open('rb') as f:
        new_db.read(f)
    assert list(new_db) == strings
