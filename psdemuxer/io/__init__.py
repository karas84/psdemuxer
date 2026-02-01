from __future__ import annotations

import os
import bisect

from io import RawIOBase, BufferedReader, BufferedIOBase
from dataclasses import dataclass

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import WriteableBuffer


@dataclass
class SegmentInfo:
    fh: BufferedIOBase
    real_address: int
    virtual_start: int
    data_size: int


class StreamReader(RawIOBase):
    def __init__(self, segment_info: list[SegmentInfo]):
        self.segment_info: list[SegmentInfo] = segment_info

        self.total_size: int = 0
        for segment in self.segment_info:
            self.total_size += segment.data_size

        self.position: int = 0
        self.offset: int = 0

    @property
    def _current_fh(self):
        return self.segment_info[self.position].fh

    @property
    def _current_pes_pos(self):
        return self.segment_info[self.position].real_address + self.offset

    @property
    def _current_virtual_pos(self):
        if self.position >= len(self.segment_info):
            return self.segment_info[-1].virtual_start + self.segment_info[-1].data_size

        return self.segment_info[self.position].virtual_start + self.offset

    @property
    def _current_chunk_size(self):
        return self.segment_info[self.position].data_size

    @property
    def _current_chunk_data_left(self):
        return self._current_chunk_size - self.offset

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._current_virtual_pos

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = self.total_size - self._current_virtual_pos

        data = b""
        left = size
        while left > 0 and self.position < len(self.segment_info):
            to_read = min(left, self._current_chunk_data_left)
            self._current_fh.seek(self._current_pes_pos)
            data_read = self._current_fh.read(to_read)
            data += data_read
            left -= len(data_read)
            self.offset += len(data_read)
            if self.offset >= self._current_chunk_size:
                self.position += 1
                self.offset = 0

        return data

    def readinto(self, buffer: WriteableBuffer) -> int | None:
        try:
            size: int = len(buffer)  # type: ignore
        except Exception:
            raise RuntimeError("cannot get size of buffer to write data to")

        data = self.read(size)

        try:
            buffer[: len(data)] = data  # type: ignore
        except Exception:
            raise RuntimeError("cannot write data in buffer")

        return len(data)

    def readall(self) -> bytes:
        return super().readall()

    def _find_seek_position(self, offset: int):
        insertion_point = bisect.bisect(self.segment_info, offset, key=lambda segment: segment.virtual_start)
        return insertion_point - 1

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_SET:
            offset = min(max(0, offset), self.total_size)

        elif whence == os.SEEK_CUR:
            offset = min(offset + self._current_virtual_pos, self.total_size)

        elif whence == os.SEEK_END:
            offset = max(0, self.total_size + min(offset, 0))

        else:
            raise ValueError(f"whence value {whence} unsupported")

        # found = 0
        # for n, segment in enumerate(self.segment_info):
        #     if segment.virtual_start > offset:
        #         found = n - 1
        #         break

        # self.position = found
        self.position = self._find_seek_position(offset)  # found
        self.offset = offset - self.segment_info[self.position].virtual_start
        return offset


class BufferedStreamReader(BufferedReader):
    def __init__(self, segment_info: list[SegmentInfo]):
        self.stream_reader = StreamReader(segment_info)
        super().__init__(self.stream_reader, buffer_size=4096)
