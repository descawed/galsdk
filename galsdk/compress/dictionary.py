# This module implements the dictionary compression algorithm that the game uses for certain TIMs. The decompression
# code is taken straight from the game and is pretty straightforward. The compression code is a big mess and generally
# sucks. As far as I can tell, the game itself doesn't contain compression code, which would make sense, as they
# would've had no reason to compress data at runtime. I wanted to reproduce the original compression exactly, but I
# haven't been able to figure out how they arrived at the specific order of entries in the dictionary that they used. I
# think they started with two-byte sequences and then built up longer sequences from those, and I tried that, but I had
# issues with overlapping sequences and the huge number of possible combinations to check. I didn't know much about
# compression, so after some research, I ended up using a suffix array and longest common prefix array to find the best,
# longest strings to add to the dictionary. This is actually pretty simple and fast, but it has the opposite problem of
# figuring out how to break the strings down. Each dictionary entry is two bytes which are recursively expanded, which
# essentially makes each string the root of a binary tree. We want the breakdown with the fewest unique nodes (which
# equates to the fewest dictionary entries). For long strings, the number of breakdowns to check is enormous. I ended up
# putting in some limits on the maximum string length and the number of possibilities to check, among other things,
# to keep the performance reasonable. Ultimately, the algorithm I've come up with is kind of complicated, not especially
# fast, and doesn't compress as well as what the devs used, but it's good enough and I'm sick of working on this code,
# so this is what it's going to be for now.
# Update 2023-12-27: After some optimizations, the speed is now significantly better, at a cost of only ~1% increase in
# file size. I think the next best target for enhancement is looking at how strings are prioritized for insertion into
# the dictionary. There should be some space-saving potential if that can be improved.
# On another note, I was informed on Discord that gdkchan actually wrote compression code for this game years ago:
# https://github.com/gdkchan/GalTTT. I considered replacing this implementation with a new one based on that code, but
# I think it's kind of a wash. While that code is faster, even after these latest optimizations, this code seems to have
# the edge in compression efficiency in the majority (but not all) of the cases I tested.

import functools
import math
import io
from collections.abc import Container
from pathlib import Path

from galsdk import file


CHUNK_SIZE = 5000  # this is accurate to how the game's original compression worked
MAX_ITERATIONS = 10000


class DictionaryCompressor:
    # these two values were chosen by trial and error based on what got the compression process to run in a reasonable
    # amount of time
    MAX_STRING_LEN = 100
    SPLIT_LENGTH_FACTOR = 11

    def __init__(self, data: bytes):
        self.data = data
        data_len = len(data)
        self.suffixes = sorted(range(data_len), key=lambda n: self.data[n:])
        self.lcp = [0] * data_len
        self.substrings = set()
        self.num_free_bytes = 0
        self.dictionary_slots = []
        self.dictionary = {}
        self.string_indexes = {}
        self.known_costs = {}

    def compress(self) -> bytes:
        data_len = len(self.data)
        if data_len == 0:
            return b''

        for i in range(data_len - 1):
            next_index = i + 1
            a = self.data[self.suffixes[next_index]:]
            b = self.data[self.suffixes[i]:]
            for j, (ac, bc) in enumerate(zip(a, b)):
                if ac != bc:
                    self.lcp[next_index] = j
                    break
            else:
                self.lcp[next_index] = min(len(a), len(b))

        # we set a limit on the maximum length of strings because it's too computationally expensive to break them down
        # for the dictionary
        self.substrings = {self.data[self.suffixes[i]:self.suffixes[i] + self.lcp[i]] for i in range(data_len) if
                           1 < self.lcp[i] <= self.MAX_STRING_LEN}
        self.remove_useless_superstrings()
        byte_map = self.create_byte_map()
        self.choose_strings(byte_map)
        final_strings = self.finalize_strings(byte_map)
        # now that we know what substrings we want to use, figure out how to construct the dictionary
        self.set_dictionary_slots()

        # prioritize highest value first, but substrings of a longer string must always come first so they're available
        # to use as components. the additional lexical sort is to make sure the result is stable.
        prioritized_strings = sorted(final_strings, key=lambda s: (final_strings[s] * len(s), len(s), s))
        while prioritized_strings:
            if len(self.dictionary) == self.num_free_bytes:
                break

            string = prioritized_strings.pop()
            # we reset this each time to keep memory usage from getting out of control
            self.known_costs = {}
            try:
                self.add_to_dictionary(string, set(prioritized_strings), final_strings)
            except OverflowError:
                pass

        raw_dictionary = self.serialize_dictionary()

        # compress the data
        compressed = bytearray()
        i = 0
        while i < data_len:
            option = byte_map[i]
            if len(option) == 0:
                compressed.append(self.data[i])
                i += 1
            else:
                (string,) = option
                str_len = len(string)
                if string in self.string_indexes:
                    compressed.append(self.string_indexes[string])
                else:
                    compressed.extend(self.data[i:i + str_len])
                i += str_len

        # finally, look for any stragglers in the data that could be compressed using entries that are in the
        # dictionary. this can happen with entries that were added to the dictionary solely to facilitate longer
        # entries, meaning they weren't around when we produced the initial byte map.
        for string, index in self.string_indexes.items():
            compressed = compressed.replace(string, bytes([index]))

        return raw_dictionary + len(compressed).to_bytes(2, 'big') + compressed

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

    def serialize_dictionary(self) -> bytes:
        raw_dictionary = bytearray()
        current = 0
        span_end = -1
        dictionary_entries = sorted((index, left, right) for index, (left, right) in self.dictionary.items())
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

    def add_to_dictionary(self, s: bytes, desired_strings: Container[bytes],
                          final_strings: dict[bytes, int] = None) -> int:
        if s in self.string_indexes:
            return self.string_indexes[s]

        str_len = len(s)
        if str_len == 1:
            return s[0]
        elif str_len == 2:
            if not self.dictionary_slots:
                raise OverflowError('Dictionary is full')

            index = self.dictionary_slots.pop()
            self.dictionary[index] = (s[0], s[1])
            self.string_indexes[s] = index
            return index

        # this string's parts aren't already part of the dictionary. in that case, find the lowest-cost way to add it
        # and use that.
        # to keep the number of comparisons reasonable, we'll divide our max by the log of the length of the string.
        # max_splits = max(int(self.SPLIT_LENGTH_FACTOR / self.log2(str_len)), 2)
        # increasing max_splits even a little bit can massively increase the compression takes, and in practice, our
        # heuristic seems to be pretty effective at finding the best split somewhere in the first few options. just take
        # the best guess and call it a day.
        max_splits = 1
        cost, new_strings, split_point = self.cost_to_add(s, self.string_indexes, 99999, desired_strings, max_splits)
        # for top-level strings, make sure the string is worth it before we add it to the dictionary
        if final_strings is not None and s in final_strings:
            value = (str_len - 1) * final_strings[s] - cost * 2
            if value < 0:
                return -1
        if len(new_strings) + len(self.string_indexes) > self.num_free_bytes:
            raise OverflowError('Maximum dictionary size exceeded')
        assert split_point > 0

        left = s[:split_point]
        right = s[split_point:]
        for sub in sorted(new_strings, key=lambda n: (len(n), n)):
            if sub != s:  # we're adding this string right now; if we try to do it again we'll get stuck in a loop
                self.add_to_dictionary(sub, desired_strings)
        # although we know we just added left and right to the dictionary, this will handle the case where one is a
        # single character without us having to repeat that logic
        left_index = self.add_to_dictionary(left, desired_strings)
        right_index = self.add_to_dictionary(right, desired_strings)
        index = self.dictionary_slots.pop()
        self.dictionary[index] = (left_index, right_index)
        self.string_indexes[s] = index
        return index

    @staticmethod
    @functools.cache
    def log2(num: int) -> float:
        return math.log(num, 2)

    @staticmethod
    def check_half(s: bytes, indexes: dict[bytes, int | None], desired_strings: Container[bytes],
                   is_odd: bool) -> tuple[int | None, bool, int, int]:
        length = len(s)
        partial_match = False
        symmetrical = 0
        repeating = 0

        index = indexes.get(s)
        if index is None:
            if length == 1:
                index = s[0]
                # we only want to prioritize these for odd-length strings because even-length strings are often
                # easier to build up from smaller pieces
                partial_match = is_odd
            elif s in desired_strings:
                # if the string isn't in the dictionary, but we want to add it to the dictionary, consider that a match
                partial_match = True
        else:
            partial_match = True

        if length & 1 != 1:
            half = length >> 1
            if s[:half] == s[half:]:
                symmetrical = 1
                if all(s[j] == s[0] for j in range(1, length)):
                    repeating = 1

        return index, partial_match, symmetrical, repeating

    def cost_to_add(self, s: bytes, indexes: dict[bytes, int | None], max_cost: int, desired_strings: Container[bytes],
                    max_splits: int = 35, max_entropy: float = 0.75) -> tuple[int, dict[bytes, int | None], int]:
        str_len = len(s)
        if s in indexes or str_len < 2:
            return 0, {}, 0  # it costs nothing to add a string that's already in the dictionary

        # we'll have to add something to the dictionary, so if any non-zero cost was unacceptable, there's no point in
        # continuing
        if max_cost <= 1:
            return 1, {}, 0

        if str_len == 2:
            return 1, {s: None}, 1  # always costs 1 to add a length-2 string

        known_strings = frozenset(indexes)
        key = (s, known_strings)
        if key in self.known_costs:
            # if we've cached the cost for this string with this dictionary, return that
            return self.known_costs[key]

        # check if there's any way to break the string down that's already in the dictionary
        is_odd = str_len & 1 == 1
        by_entropy = []
        known_combos = set()
        for i in range(1, str_len):
            left = s[:i]
            right = s[i:]
            right_len = len(right)

            left_index, left_partial_match, left_symmetrical, left_repeating = self.check_half(left, indexes,
                                                                                               desired_strings, is_odd)
            right_index, right_partial_match, right_symmetrical, right_repeating = self.check_half(right, indexes,
                                                                                                   desired_strings,
                                                                                                   is_odd)
            neg_partial_match_len = i if left_partial_match else right_len if right_partial_match else -1

            if left_index is not None and right_index is not None:
                new_index = {s: None}
                self.known_costs[(s, known_strings)] = (1, new_index, i)
                return 1, new_index, i

            # as we go, keep a list of possible splits prioritized by minimizing the average "entropy" of the pair, as
            # strings with a lower number of unique bytes relative to their length should be possible to store more
            # efficiently. the negative is because we want splits that have a partial match to sort before strings that
            # don't. finally, we put i last because it's the length of the left string, and we check the left string
            # first. that means that, if the two strings are nearly identical (common in long strings to have the same
            # byte repeated over and over) but one is longer (perhaps because the length is odd), the shorter string
            # will be inserted first and will be available as a component for the longer one.
            pair = frozenset((left, right))
            if pair in known_combos:
                continue

            known_combos.add(pair)
            repeating = left_repeating + right_repeating
            symmetrical = left_symmetrical + right_symmetrical
            by_entropy.append((-neg_partial_match_len, -repeating, -symmetrical,
                               (len(set(left)) / i + len(set(right)) / right_len) / 2, i))

        # at this point, the best cost we can hope for is 2: 1 for ourselves and 1 for at least one substring we'll need
        # to add. so if the max cost is 2 or less, we should give up now.
        if max_cost <= 2:
            return 2, {}, 0

        by_entropy.sort()

        # if not, do the slow analysis
        best_cost = max_cost
        new_indexes = {}
        split_index = 0
        # to keep the number of comparisons reasonable, we only consider the first max_splits options
        for neg_partial_match_len, _, _, entropy, i in by_entropy[:max_splits]:
            left_cost, left_indexes, _ = self.cost_to_add(s[:i], indexes, best_cost, desired_strings, max_splits)
            if left_cost >= best_cost:
                continue
            right_cost, right_indexes, _ = self.cost_to_add(s[i:], left_indexes | indexes, best_cost - left_cost,
                                                            desired_strings, max_splits)
            cost = left_cost + right_cost
            if best_cost > cost:
                best_cost = cost
                # we don't care about putting an actual value here since this is just a hypothetical at this point
                new_indexes = left_indexes | right_indexes | {s: None}
                split_index = i
                self.known_costs[(s, known_strings)] = (best_cost + 1, new_indexes, i)
                # if the cost could be 0, we would have found a match in the loop above, so if we find a cost of 1,
                # that's the best we can do
                if cost == 1:
                    break
            # if the entropy is very high and we don't have a partial match, we're probably not going to do much better,
            # so give up and take what we've got
            if entropy > max_entropy and neg_partial_match_len > 0:
                break

        # +1 for ourselves
        return best_cost + 1, new_indexes, split_index

    def set_dictionary_slots(self):
        used_bytes = set(self.data)
        free_bytes = sorted(set(range(256)) - used_bytes)
        self.num_free_bytes = len(free_bytes)
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

        self.dictionary_slots = [free_bytes[i] for r in sorted(filter(None, ranges), key=lambda r: (len(r), r.start))
                                 for i in r]

    def finalize_strings(self, byte_map: list[set[bytes]]) -> dict[bytes, int]:
        # make a final pass to remove strings that are no longer useful
        data_len = len(self.data)
        chosen_strings = {ss for s in byte_map for ss in s}
        strings_to_remove = set()
        while True:
            num_chosen_strings = len(chosen_strings)
            superstrings = {s for s in chosen_strings if all(s not in ss or s == ss for ss in chosen_strings)}
            usage_counts = {}
            i = 0
            while i < data_len:
                choice = byte_map[i]
                if len(choice) == 0:
                    i += 1
                    continue

                (string,) = choice
                if string not in usage_counts:
                    usage_counts[string] = 1
                else:
                    usage_counts[string] += 1
                i += len(string)

            for string in superstrings:
                if usage_counts[string] < 2:
                    chosen_strings.remove(string)
                    strings_to_remove.add(string)
                    del usage_counts[string]

            if len(chosen_strings) == num_chosen_strings:
                break

        for i in range(data_len):
            # each byte only has a single string at this point, so if the sets overlap, the chosen string for the byte
            # is no longer valid
            if byte_map[i] & strings_to_remove:
                byte_map[i] = set()

        return usage_counts

    def choose_strings(self, byte_map: list[set[bytes]], start: int = 0, end: int = None,
                       candidate: bytes = None) -> int:
        map_len = len(byte_map)
        if end is None:
            end = map_len
        min_len = len(candidate) if candidate is not None else 0
        i = start
        first_index_set = end
        while i < end:
            this_set = byte_map[i]
            if candidate is not None and candidate not in this_set:
                # if we have a candidate, we're checking to see if the caller can substitute this range of bytes with
                # the candidate. so, if the candidate isn't in our set, it's not valid for this byte, and we should tell
                # the caller not to use the candidate by telling it to truncate its strings at this index
                return i

            if len(this_set) == 0:
                i += 1
                continue

            sorted_set = sorted(this_set, key=len)
            while sorted_set:
                s = sorted_set.pop()
                str_len = len(s)
                if str_len <= min_len:
                    # when we're checking the validity of a candidate string, we only care about strings that are longer
                    # than the candidate
                    i += 1
                    break
                sub_end = i + str_len
                if self.data[i:sub_end] != s:
                    # this string is no longer valid because we replaced its starting byte with a shorter string
                    this_set.remove(s)
                    continue
                # make sure none of the bytes this change will cover have a better substitution
                truncate_at = self.choose_strings(byte_map, i + 1, sub_end, s)
                if truncate_at < sub_end:
                    # the string we wanted either overlaps with a better string further down the line or is no longer
                    # valid because it's part of a sequence we already replaced, so remove it and try again
                    this_set.remove(s)
                    continue
                # this string doesn't overlap; choose it
                if i < first_index_set:
                    first_index_set = i
                for j in range(i, sub_end):
                    byte_map[j] = {s}
                i = sub_end
                break

        return first_index_set

    def create_byte_map(self) -> list[set[bytes]]:
        byte_options = [set() for _ in range(len(self.data))]
        for i, p in enumerate(self.lcp):
            if p > 1:
                index = self.suffixes[i]
                end = index + p
                string = self.data[index:end]
                # the full prefix might have been removed from the list of substrings, so see if there's a smaller
                # prefix that still works
                while string not in self.substrings and len(string) >= 2:
                    string = string[:-1]

                str_len = len(string)
                if str_len < 2:
                    continue

                end = index + str_len
                while index != -1:
                    for j in range(index, end):
                        byte_options[j].add(string)
                    index = self.data.find(string, end)
                    end = index + str_len

                # because of the way the LCP array works, if the string before us was the first string in the sequence
                # of strings that start with this prefix, it could have missed it because it didn't have enough in
                # common with the string before it. so we also need to push this string back to that index.
                if i > 0:
                    last_i = i - 1
                    last_p = self.lcp[last_i]
                    if last_p < str_len:
                        index = self.suffixes[last_i]
                        end = index + str_len
                        assert self.data[index:end] == string
                        for j in range(index, end):
                            byte_options[j].add(string)

        return byte_options

    def remove_useless_superstrings(self):
        known_good = set()
        data_len = len(self.data)
        while True:
            num_substrings = len(self.substrings)
            sub_substrings = set()
            # we'll identify all the strings that are prefixes of another string, which we can do quickly
            i = 0
            while i < data_len:
                p = self.lcp[i]
                index = self.suffixes[i]
                string = self.data[index:index + p]
                if p > 1 and string in self.substrings:
                    for j in range(i + 1, data_len):
                        p2 = self.lcp[j]
                        if p2 != p:
                            index = self.suffixes[j]
                            next_string = self.data[index:index + p2]
                            if p2 > p:
                                if next_string not in self.substrings:
                                    continue  # this string has been removed, so we aren't a substring of it
                                sub_substrings.add(string)
                                i = j
                            else:
                                if p2 > 1:
                                    sub_substrings.add(next_string)
                                i = j + 1
                            break
                    else:
                        i += 1
                else:
                    i += 1

            superstrings = self.substrings - sub_substrings - known_good
            for superstring in superstrings:
                if self.data.count(superstring) <= 2:
                    self.substrings.remove(superstring)
                else:
                    known_good.add(superstring)

            if len(self.substrings) == num_substrings:
                break


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
