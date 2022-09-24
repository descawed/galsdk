from galsdk.db import Database


def test_db(tmp_path):
    first_file = b'this is the first file'
    second_file = b'this is the second file'
    cdb_path = tmp_path / 'test.cdb'
    db = Database()
    db.append(first_file)
    db.append(second_file)
    with cdb_path.open('wb') as f:
        db.write(f)

    new_db = Database()
    with cdb_path.open('rb') as f:
        new_db.read(f)
    assert len(new_db) == 2
    assert new_db[0].startswith(first_file) and all(b == 0 for b in new_db[0][len(first_file):])
    assert new_db[1].startswith(second_file) and all(b == 0 for b in new_db[1][len(second_file):])


def test_extended_db(tmp_path):
    first_file = b'this is the first file'
    second_file = b'this is the second file'
    cdb_path = tmp_path / 'test.cdb'
    db = Database(True)
    db.append(first_file)
    db.append(second_file)
    with cdb_path.open('wb') as f:
        db.write(f)

    new_db = Database()
    with cdb_path.open('rb') as f:
        new_db.read(f)
    assert len(new_db) == 2
    assert new_db[0] == first_file
    assert new_db[1] == second_file
