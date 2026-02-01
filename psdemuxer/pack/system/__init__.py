from __future__ import annotations

from io import BufferedReader

from psdemuxer.utils import peek
from psdemuxer.pack.system.streamid import StreamId, StreamIdEx
from psdemuxer.exceptions import InvalidMarkerException


class SystemHeader:
    start_code = b"\x00\x00\x01\xbb"
    size = 12

    def __init__(self, fh: BufferedReader):
        self.pos = fh.tell()
        self.data: bytearray = bytearray(SystemHeader.size)
        self.streams: list[StreamId | StreamIdEx] = []

        fh.readinto(self.data)
        assert self.header == SystemHeader.start_code, f"{self.header} != {SystemHeader.start_code}"

        if not self.marker_0 or not self.marker_1 or not self.marker_2:
            raise InvalidMarkerException()

        next_bits = peek(fh, 1)

        while next_bits[0] & 0b10000000:
            stream_id = next_bits[0]
            if stream_id == StreamIdEx.stream_id_ex:
                s_id = StreamIdEx(fh)
            else:
                s_id = StreamId(fh)

            self.streams.append(s_id)

            next_bits = peek(fh, 1)

    @property
    def header(self):
        return self.data[:4]

    @property
    def header_length(self) -> int:
        # fmt: off
        return \
            ((self.data[4] & 0b11111111) >> 0) << 8 | \
            ((self.data[5] & 0b11111111) >> 0) << 0
        # fmt: on

    @property
    def rate_bound(self) -> int:
        # fmt: off
        return \
            ((self.data[6] & 0b01111111) >> 0) << 15 | \
            ((self.data[7] & 0b11111111) >> 0) << 7 | \
            ((self.data[8] & 0b11111110) >> 1) << 0
        # fmt: on

    @property
    def audio_bound(self) -> int:
        return (self.data[9] & 0b01111100) >> 2

    @property
    def fixed_flag(self) -> int:
        return (self.data[9] & 0b000000010) >> 1

    @property
    def csps_flag(self) -> int:
        return (self.data[9] & 0b000000001) >> 0

    @property
    def system_audio_lock_flag(self) -> int:
        return (self.data[10] & 0b100000000) >> 7

    @property
    def system_video_lock_flag(self) -> int:
        return (self.data[10] & 0b01000000) >> 6

    @property
    def video_bound(self) -> int:
        return (self.data[10] & 0b00011111) >> 0

    @property
    def packet_rate_restriction_flag(self) -> int:
        return (self.data[11] & 0b10000000) >> 7

    @property
    def reserved_bits(self) -> int:
        return (self.data[11] & 0b01111111) >> 0

    @property
    def marker_0(self) -> int:
        return (self.data[6] & 0b10000000) >> 7

    @property
    def marker_1(self) -> int:
        return (self.data[8] & 0b00000001) >> 0

    @property
    def marker_2(self) -> int:
        return (self.data[10] & 0b00100000) >> 5

    def __str__(self) -> str:
        str_ = f"-- 0x{self.pos:X} SystemHeader --\n"
        str_ += "\n".join(
            [
                f"header=0x{self.header.hex().upper()}",
                f"header_length={self.header_length}",
                f"rate_bound={self.rate_bound}",
                f"audio_bound={self.audio_bound}",
                f"fixed_flag={self.fixed_flag}",
                f"csps_flag={self.csps_flag}",
                f"system_audio_lock_flag={self.system_audio_lock_flag}",
                f"system_video_lock_flag={self.system_video_lock_flag}",
                f"video_bound={self.video_bound}",
                f"packet_rate_restriction_flag={self.packet_rate_restriction_flag}",
                f"reserved_bits={self.reserved_bits}",
                f"streams={len(self.streams)}",
            ]
        )
        for stream in self.streams:
            str_ += "\n" + str(stream)
        return str_

    def __repr__(self) -> str:
        return f"----- 0x{self.pos:08X} 0x{self.header.hex().upper()}"
