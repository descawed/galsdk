import io
from collections import defaultdict
from pathlib import Path

from galsdk import file


CHUNK_SIZE = 5000  # this is accurate to how the game's original compression worked
MAX_ITERATIONS = 10000


class DictionaryCompressor:
    MIN_OCCURRENCES = 3

    def __init__(self, data: bytes):
        self.data = data

    def compress(self) -> bytes:
        # thanks to Marco Calautti for help with this algorithm
        # https://github.com/marco-calautti/GaleriansTools
        # https://github.com/descawed/galsdk/issues/23
        dictionary_slots = self.sort_dictionary_slots()

        dictionary = {}
        buf = self.data
        while dictionary_slots:
            frequencies = defaultdict(int)
            max_frequency = 0
            best_sequence = None
            for i in range(len(buf) - 1):
                sequence = buf[i:i + 2]
                frequency = frequencies[sequence] + 1
                frequencies[sequence] = frequency
                if frequency > max_frequency:
                    max_frequency = frequency
                    best_sequence = sequence

            if max_frequency < self.MIN_OCCURRENCES:
                break

            dictionary_byte = dictionary_slots.pop()
            dictionary[dictionary_byte] = (best_sequence[0], best_sequence[1])
            buf = buf.replace(best_sequence, bytes([dictionary_byte]))

        return self.serialize_dictionary(dictionary) + len(buf).to_bytes(2, 'big') + buf

    @staticmethod
    def start_span(count: int, start: int, entries: list[tuple[int, int, int]]) -> int:
        last_index = start
        for next_j, _, _ in entries:
            diff = next_j - last_index
            # we allow a gap of 2 because it's still more efficient to write a dummy value than to advance the index
            if diff <= 2:
                count += diff
                last_index = next_j
            else:
                break
        if count >= 0x80:
            count = 0x7f
        return count

    def serialize_dictionary(self, dictionary: dict[int, tuple[int, int]]) -> bytes:
        raw_dictionary = bytearray()
        current = 0
        span_end = -1
        dictionary_entries = sorted((index, left, right) for index, (left, right) in dictionary.items())
        for i, (j, left, right) in enumerate(dictionary_entries):
            if current < j:
                diff = j - current
                if diff == 1 and (current <= span_end or i + 1 >= len(dictionary_entries) or dictionary_entries[i + 1][0] <= j + 2):
                    if current > span_end:
                        count = self.start_span(1, j, dictionary_entries[i + 1:])
                        raw_dictionary.append(count)
                        span_end = current + count
                    # more efficient to just write a dummy value than have to advance the index
                    raw_dictionary.append(current)
                    current += 1
                else:
                    if diff > 0x80:
                        diff -= 0x80
                        current += 0x80
                        raw_dictionary.append(0xff)
                        raw_dictionary.append(current)
                        current += 1
                        diff -= 1
                    if diff > 0:
                        raw_dictionary.append(diff + 0x7f)
                        current += diff
            elif current > span_end:
                count = self.start_span(0, j, dictionary_entries[i + 1:])
                raw_dictionary.append(count)
                span_end = current + count
            raw_dictionary += bytes([left, right])
            current += 1

        if current < 256:
            diff = 256 - current
            if diff > 0x80:
                diff -= 0x80
                current += 0x80
                raw_dictionary.append(0xff)
                raw_dictionary.append(current)
                current += 1
                diff -= 1
            if diff > 0:
                raw_dictionary.append(diff + 0x7f)

        return bytes(raw_dictionary)

    def sort_dictionary_slots(self) -> list[int]:
        free_bytes = sorted(set(range(256)) - set(self.data))
        # find the best order to allocate dictionary slots in order to make the most efficient use of space
        last_value = free_bytes[0]
        start = 0
        ranges = []
        for i, b in enumerate(free_bytes):
            diff = b - last_value
            if diff > 1:
                ranges.append(range(start, i))
                start = i
            last_value = b
        ranges.append(range(start, len(free_bytes)))

        return [free_bytes[i] for r in sorted(filter(None, ranges), key=lambda r: (len(r), r.start)) for i in r]


def compress(data: bytes) -> bytes:
    final_data = bytearray()
    for i in range(0, len(data), CHUNK_SIZE):
        compressor = DictionaryCompressor(data[i:i + CHUNK_SIZE])
        chunk_data = compressor.compress()
        final_data.extend(chunk_data)

    final_data_len = len(final_data)
    padding_needed = (4 - final_data_len & 3) & 3
    if padding_needed > 0:
        final_data += b'0' * padding_needed

    return final_data_len.to_bytes(4, 'little') + final_data


def decompress(data: bytes) -> list[tuple[int, bytes]]:
    # not sure what this compression algorithm is, if it even is a well-known algorithm. it seems to take advantage
    # of the fact that the data being compressed doesn't contain all possible byte values, so it maps the unused
    # values to sequences of two values, which are recursively expanded. initially, all values are mapped to
    # themselves, so they would be output literally. the first part of the data encodes the mapped dictionary
    # sequences. the second part (starting from stream_len) is the actual compressed data.
    results = []
    stream_end = len(data)
    with io.BytesIO(data) as f:
        # a single data stream can contain multiple compressed TIMs one after another, so decompress repeatedly
        # until we reach the end of the data
        while f.tell() < stream_end:
            offset = f.tell()
            output = bytearray()
            data_len = file.int_from_bytes(f.read(4))
            if data_len == 0:
                break
            if data_len > stream_end - f.tell():
                raise EOFError('EOF encountered while decompressing TIM')
            data_end = f.tell() + data_len
            while f.tell() < data_end:
                dictionary = [(i, i) for i in range(0x100)]
                index = 0
                while index != 0x100:
                    # we select an index into the dictionary and/or a number of entries to update
                    byte = f.read(1)[0]
                    if byte < 0x80:
                        # if byte < 0x80, populate `count` contiguous indexes in the dictionary starting from the
                        # current index
                        count = byte + 1
                    else:
                        # otherwise, we update our dictionary index and populate only that index
                        index += byte - 0x7f
                        count = 1

                    for _ in range(count):
                        if index == 0x100:
                            break
                        byte = f.read(1)[0]
                        dictionary[index] = (byte, byte)
                        if byte != index:
                            dictionary[index] = (byte, f.read(1)[0])
                        index += 1

                stream_len = file.int_from_bytes(f.read(2), 'big')
                end = f.tell() + stream_len
                while f.tell() != end:
                    stack = [f.read(1)[0]]
                    i = 0
                    while len(stack) > 0:
                        index = stack.pop()
                        values = dictionary[index]
                        if values[0] == index:
                            output.append(values[0])
                        else:
                            # push in reverse order so they'll be popped in the right order
                            stack.append(values[1])
                            stack.append(values[0])
                        i += 1
                        if i > MAX_ITERATIONS:
                            raise RuntimeError('The decompression routine appears to be stuck in an infinite loop')
            results.append((offset, bytes(output)))
            # data is padded out to a multiple of 4 with '0' characters
            padding_needed = (4 - data_len & 3) & 3
            if padding_needed > 0:
                padding = f.read(padding_needed)
                if not all(c in [0, 0x30] for c in padding):
                    raise ValueError('Expected padding bytes')

    return results


def cli_compress(output_path: Path, input_paths: list[Path]):
    with output_path.open('wb') as f:
        for input_path in input_paths:
            f.write(compress(input_path.read_bytes()))


def cli_decompress(input_path: Path, output_path: Path):
    files = decompress(input_path.read_bytes())
    for i, (_, data) in enumerate(files):
        if output_path.is_dir():
            file_path = output_path / f'{i:02}.TIM'
        elif len(files) > 1:
            file_path = output_path.with_stem(output_path.stem + f'_{i:02}')
        else:
            file_path = output_path
        file_path.write_bytes(data)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Compress or decompress files using the Galerians dictionary compression algorithm',
    )
    subparsers = parser.add_subparsers(required=True)

    compress_parser = subparsers.add_parser('compress', help='Compress one or more files')
    compress_parser.add_argument('output', type=Path, help='Compressed output file')
    compress_parser.add_argument('files', nargs='+', type=Path, help='Files to compress')
    compress_parser.set_defaults(action=lambda a: cli_compress(a.output, a.files))

    decompress_parser = subparsers.add_parser('decompress', help='Decompress a file')
    decompress_parser.add_argument('input', type=Path, help='Compressed input file')
    decompress_parser.add_argument('output', type=Path, help='Decompressed output file(s). May be a directory.')
    decompress_parser.set_defaults(action=lambda a: cli_decompress(a.input, a.output))

    args = parser.parse_args()
    args.action(args)
