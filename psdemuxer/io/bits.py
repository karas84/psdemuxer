from __future__ import annotations

from io import BufferedIOBase, BytesIO
from math import ceil
from functools import lru_cache


class BitStreamReader:
    def __init__(self, fh: BufferedIOBase, keep_data: bool = False) -> None:
        self._fh: BufferedIOBase = fh
        self._keep_data: bool = keep_data
        self._position: int = 0
        self._current_byte: int = 0
        self._data: BytesIO | None = None

        if self._keep_data:
            self._data = BytesIO()

    @lru_cache(maxsize=64)
    def _make_mask(self, num: int, pos: int):
        if num + pos > 8:
            raise ValueError("invalid num and pos combination")
        mask = (2**num - 1) << (8 - num - pos)
        shift = 8 - num - pos
        return mask, shift

    def read(self, size: int):
        if self._position == 0:
            data = self._fh.read(1)
            self._current_byte = data[0]
            if self._data is not None:
                self._data.write(data)

        bits_in_current_pos: int = 8 - self._position
        extra_bits_to_read: int = max(0, size - bits_in_current_pos)
        extra_byte_num: int = ceil(extra_bits_to_read / 8)
        extra_bytes = self._fh.read(extra_byte_num)
        value: int = 0
        bits_left_to_shift: int = size

        num = min(size, bits_in_current_pos)
        mask, right_shift = self._make_mask(num, self._position)
        left_shift = bits_left_to_shift - num
        value = value | (((self._current_byte & mask) >> right_shift) << left_shift)
        bits_left_to_shift -= num
        new_pos: int = (self._position + num) % 8

        for extra_byte in extra_bytes:
            num = min(8, extra_bits_to_read)
            mask, right_shift = self._make_mask(num, pos=0)
            left_shift = bits_left_to_shift - num
            value = value | (((extra_byte & mask) >> right_shift) << left_shift)
            bits_left_to_shift -= num
            extra_bits_to_read -= num
            new_pos = num % 8
            self._current_byte = extra_byte

        self._position = new_pos

        if self._data is not None:
            self._data.write(extra_bytes)

        return value

    def get_data(self) -> bytes | None:
        if self._data is None:
            return None

        return self._data.getvalue()


def b(num: int):
    return f"0b{num:08b}"


def make_bytes(*bb: int):
    res = b""
    for b in bb:
        res += b.to_bytes(1, "little")
    return res


def test_make_mask():
    for i in range(8 + 1):
        for j in range(8 + 1 - i):
            mask, shift = BitStreamReader._make_mask(None, i, j)  # type: ignore
            print(f"{i}, {j}: {b(mask)} >> {shift}")


def test_bit_read():
    import time
    import random
    from io import BytesIO

    num_bytes = 1 * 1024 * 1024
    byte_stream_str = "".join([str(random.randint(0, 1)) for _ in range(8 * num_bytes)])
    byte_chunks = [byte_stream_str[i : i + 8] for i in range(0, len(byte_stream_str), 8)]
    byte_stream = bytes([int(val, 2) for val in byte_chunks])

    s = ""
    for val in byte_stream:
        s += f"{val:08b}"
    assert s == byte_stream_str

    chunk_lengths: list[int] = []
    bit_left = len(byte_stream_str)
    while bit_left > 0:
        length = random.randint(1, min(bit_left, 32))
        chunk_lengths.append(length)
        bit_left -= length

    # print(chunk_lengths)

    pos: int = 0
    lst: list[str] = []
    for length in chunk_lengths:
        byte_str = byte_stream_str[pos : pos + length]
        lst.append(byte_str)
        pos += length

    # print(lst)

    data = BytesIO(byte_stream)
    bsr = BitStreamReader(data, keep_data=True)

    t = time.perf_counter()

    pos = 0
    for _n, (length, byte_str) in enumerate(zip(chunk_lengths, lst)):
        # if _n % 1000 == 0:
        #     print(_n, len(chunk_lengths))
        expected_val = int(byte_str, 2)
        pos = (pos + length) % 8
        val = bsr.read(length)
        assert val == expected_val, f"0b{val:b} != 0b{byte_str}"
        assert bsr._position == pos, f"{pos} != {bsr._position}"  # type: ignore

    data_read = bsr.get_data()
    assert data_read is not None
    assert len(data_read) == num_bytes

    t = time.perf_counter() - t
    bits_per_second = (num_bytes * 8) / t
    print(f"Done in {t:.3f} seconds ({bits_per_second / 1024:.0f} kbps)")


# test_bit_read()
