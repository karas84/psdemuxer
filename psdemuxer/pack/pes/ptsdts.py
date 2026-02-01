from __future__ import annotations

from io import BufferedReader

from typing import TYPE_CHECKING

from psdemuxer.exceptions import InvalidFixedBitsException

if TYPE_CHECKING:
    from psdemuxer.pack.pes import FlagData


class PTS:
    def __init__(self, pts: int):
        self.pts = pts

        pts_ms = pts / 90

        self.microseconds = int((pts_ms / 1000) % 1 * 1e6)
        self.seconds = int((pts_ms / 1000) % 60)
        self.minutes = int((pts_ms / (1000 * 60)) % 60)
        self.hours = int((pts_ms / (1000 * 60 * 60)) % 24)

    def __str__(self) -> str:
        return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}.{self.microseconds:06d}"


class FlagPTS:
    def __init__(self, pes_pfd: FlagData, fh: BufferedReader):
        self.pes_pfd: FlagData = pes_pfd
        self.data: bytearray = bytearray(5)

        fh.readinto(self.data)

        if self.b_0010 != 0b0010:
            raise InvalidFixedBitsException()

    @property
    def b_0010(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def pts(self) -> PTS:
        return PTS(
            ((self.data[0] & 0b00001110) >> 1) << 30
            | ((self.data[1] & 0b11111111) >> 0) << 22
            | ((self.data[2] & 0b11111110) >> 1) << 15
            | ((self.data[3] & 0b11111111) >> 0) << 7
            | ((self.data[4] & 0b11111110) >> 1) << 0
        )

    @property
    def c0(self) -> int:
        return (self.data[0] & 0b00000001) >> 0

    @property
    def c1(self) -> int:
        return (self.data[2] & 0b00000001) >> 0

    @property
    def c2(self) -> int:
        return (self.data[4] & 0b00000001) >> 0

    def __str__(self) -> str:
        return f"PTS=0x{self.pts.pts:010X} ({self.pts})\n"


class FlagPTSDTS:
    def __init__(self, pes_pfd: FlagData, fh: BufferedReader):
        self.pes_pfd: FlagData = pes_pfd
        self.data: bytearray = bytearray(10)

        fh.readinto(self.data)

        if self.b_0011 != 0b0011 or self.b_0001 != 0b0001:
            raise InvalidFixedBitsException()

    @property
    def b_0011(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def pts(self) -> PTS:
        return PTS(
            ((self.data[0] & 0b00001110) >> 1) << 30
            | ((self.data[1] & 0b11111111) >> 0) << 22
            | ((self.data[2] & 0b11111110) >> 1) << 15
            | ((self.data[3] & 0b11111111) >> 0) << 7
            | ((self.data[4] & 0b11111110) >> 1) << 0
        )

    @property
    def b_0001(self) -> int:
        return (self.data[5] & 0b11110000) >> 4

    @property
    def dts(self) -> PTS:
        return PTS(
            ((self.data[5] & 0b00001110) >> 1) << 30
            | ((self.data[6] & 0b11111111) >> 0) << 22
            | ((self.data[7] & 0b11111110) >> 1) << 15
            | ((self.data[8] & 0b11111111) >> 0) << 7
            | ((self.data[9] & 0b11111110) >> 1) << 0
        )

    @property
    def c0(self) -> int:
        return (self.data[0] & 0b00000001) >> 0

    @property
    def c1(self) -> int:
        return (self.data[2] & 0b00000001) >> 0

    @property
    def c2(self) -> int:
        return (self.data[4] & 0b00000001) >> 0

    @property
    def c3(self) -> int:
        return (self.data[5] & 0b00000001) >> 0

    @property
    def c4(self) -> int:
        return (self.data[7] & 0b00000001) >> 0

    @property
    def c5(self) -> int:
        return (self.data[9] & 0b00000001) >> 0

    def __str__(self) -> str:
        # fmt: off
        return (
            f"PTS=0x{self.pts.pts:010X} ({self.pts})\n"
            f"DTS=0x{self.dts.pts:010X} ({self.dts})\n"
        )
        # fmt: on
