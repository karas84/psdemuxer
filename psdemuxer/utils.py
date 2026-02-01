from __future__ import annotations

import os

from io import BufferedReader

from psdemuxer.constants import start_code_prefix
from psdemuxer.exceptions import MPEG2FileFormatException


def next_start_code(fh: BufferedReader, check_zeros: bool = True):
    found = False
    while not found:
        data = peek(fh, 3)
        found = data == start_code_prefix
        if not found:
            zero_byte = fh.read(1)
            if check_zeros and zero_byte != b"\x00":
                raise MPEG2FileFormatException("non zero padding bytes while looking dor extension start code")


def peek(fh: BufferedReader, size: int):
    data = fh.peek(size)[:size]
    if len(data) != size:
        data = fh.read(size)
        fh.seek(-size, os.SEEK_CUR)
    assert len(data) == size
    return data


def bytearray_resize(array: bytearray, new_size: int):
    new_array = bytearray(new_size)
    new_array[: len(array)] = array
    return new_array


def bytearray_extend(array: bytearray, extend_size: int):
    new_size = len(array) + extend_size
    return bytearray_resize(array, new_size)


def bytearray_append(array: bytearray, extra: bytearray | bytes):
    old_size = len(array)
    new_size = old_size + len(extra)
    array = bytearray_resize(array, new_size)
    array[old_size:] = extra
    return array
