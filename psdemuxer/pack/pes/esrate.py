from __future__ import annotations

from io import BufferedReader

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psdemuxer.pack.pes.flagdata import FlagData


class FlagESRate:
    def __init__(self, pes_pfd: FlagData, fh: BufferedReader):
        self.pes_pfd: FlagData = pes_pfd
        self.data: bytearray = bytearray(3)

        fh.readinto(self.data)

    @property
    def es_rate(self) -> int:
        # fmt: off
        return \
            ((self.data[0] & 0b01111111) >> 0) << 15 | \
            ((self.data[1] & 0b11111111) >> 0) << 7 | \
            ((self.data[2] & 0b11111110) >> 1) << 0
        # fmt: on

    @property
    def c0(self) -> int:
        return (self.data[0] & 0b10000000) >> 7

    @property
    def c1(self) -> int:
        return (self.data[2] & 0b00000001) >> 0

    def __str__(self) -> str:
        return f"ES_rate=0x{self.es_rate:X}\n"
