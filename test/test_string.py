from galsdk.string import StringDb


def test_read_write(tmp_path):
    test_path = str(tmp_path / 'string.db')
    strings = ['first string', 'second string', 'hello world']

    db = StringDb()
    for string in strings:
        db.append(string)
    db.write(test_path)

    new_db = StringDb()
    new_db.read(test_path)
    assert list(new_db) == strings
