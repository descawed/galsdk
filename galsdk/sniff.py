import pathlib
import sys

from galsdk.db import Database
from galsdk.format import FileFormat
from galsdk.menu import Menu
from galsdk.model import ActorModel, ItemModel
from galsdk.module import RoomModule
from galsdk.string import LatinStringDb, JapaneseStringDb
from galsdk.tim import TimFormat, TimDb
from galsdk.vab import VabDb
from galsdk.xa import XaDatabase


# TimDb needs to come before TimFormat in the list because TimFormat will miss additional images in TIM streams
formats: list[type[FileFormat]] = [LatinStringDb, XaDatabase, Menu, TimDb, TimFormat, Database, VabDb, RoomModule,
                                   ActorModel, ItemModel, JapaneseStringDb]


def sniff_file(path: pathlib.Path, formats_to_check: list[type[FileFormat]] = None) -> FileFormat | None:
    if formats_to_check is None:
        formats_to_check = formats
    with path.open('rb') as f:
        for file_format in formats_to_check:
            f.seek(0)
            if result := file_format.sniff(f):
                return result
    return None


def sniff_paths(paths: list[str | pathlib.Path], export_path: str | pathlib.Path = None, rename: bool = False,
                counter: int = 0, formats_to_check: list[type[FileFormat]] = None) -> int:
    if formats_to_check is None:
        formats_to_check = formats
    if export_path is not None and not isinstance(export_path, pathlib.Path):
        export_path = pathlib.Path(export_path)
    for path in paths:
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)
        if path.is_dir():
            counter = sniff_paths(list(path.iterdir()), export_path, rename, counter, formats_to_check)
        elif result := sniff_file(path, formats_to_check):
            print(f'{path} was detected to be a {result.suggested_extension} file')
            if rename:
                path = path.rename(path.with_suffix(result.suggested_extension))
            if export_path:
                file_path = export_path / f'{path.stem}_export{counter}'
                try:
                    final_path = result.export(file_path)
                    print(f'\t{path} was exported to {final_path}')
                except NotImplementedError:
                    print(f'\t{path} does not support exporting')
            counter += 1
        else:
            print(f'The format of {path} could not be determined', file=sys.stderr)

    return counter


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Detect file format of Galerians files')
    parser.add_argument('-r', '--rename', help="Rename files with the detected format's suggested extension",
                        action='store_true')
    parser.add_argument('-x', '--export', help='Export identified files in a default format to the given directory')
    parser.add_argument('files', nargs='+', help='Files to sniff. Directories will be explored recursively.')

    args = parser.parse_args()
    sniff_paths(args.files, args.export, args.rename)
