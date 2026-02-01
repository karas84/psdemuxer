from __future__ import annotations

from io import BufferedReader

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psdemuxer.pack.pes.flagdata import FlagData


class FlagESCR:
    def __init__(self, pes_pfd: FlagData, fh: BufferedReader):
        self.pes_pfd: FlagData = pes_pfd
        self.data: bytearray = bytearray(6)

        fh.readinto(self.data)

    @property
    def reserved(self) -> int:
        return (self.data[0] & 0b11000000) >> 6

    @property
    def escr_base(self) -> int:
        # fmt: off
        return \
            ((self.data[0] & 0b00111000) >> 3) << 30 | \
            ((self.data[0] & 0b00000011) >> 0) << 28 | \
            ((self.data[1] & 0b11111111) >> 0) << 20 | \
            ((self.data[2] & 0b11111000) >> 3) << 15 | \
            ((self.data[2] & 0b00000011) >> 0) << 13 | \
            ((self.data[3] & 0b11111111) >> 0) << 5 | \
            ((self.data[4] & 0b11111000) >> 3) << 0
        # fmt: on

    @property
    def escr_ext(self) -> int:
        # fmt: off
        return \
            ((self.data[4] & 0b00000011) >> 0) << 7 | \
            ((self.data[4] & 0b11111110) >> 1) << 0
        # fmt: on

    @property
    def c0(self) -> int:
        return (self.data[0] & 0b00000100) >> 2

    @property
    def c1(self) -> int:
        return (self.data[2] & 0b00000100) >> 2

    @property
    def c2(self) -> int:
        return (self.data[4] & 0b00000100) >> 2

    @property
    def c3(self) -> int:
        return (self.data[4] & 0b00000001) >> 0

    def __str__(self) -> str:
        # fmt: off
        return (
            f"reserved=0b{self.reserved:b}\n"
            f"ESCR_base=0x{self.escr_base:X}\n"
            f"ESCR_extension=0x{self.escr_ext:X}\n"
        )
        # fmt: on
