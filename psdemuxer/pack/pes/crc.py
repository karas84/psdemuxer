from __future__ import annotations

from io import BufferedReader

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psdemuxer.pack.pes.flagdata import FlagData


class CRCFlag:
    def __init__(self, pes_pfd: FlagData, fh: BufferedReader):
        self.pes_pfd: FlagData = pes_pfd
        self.data: bytearray = bytearray(2)

        fh.readinto(self.data)

    @property
    def previous_pes_packet_crc(self) -> int:
        # fmt: off
        return (((self.data[0] & 0b11111111) >> 0) << 8) | \
               (((self.data[1] & 0b11111111) >> 0) << 0)
        # fmt: on

    def __str__(self) -> str:
        return f"previous_PES_packet_CRC=0x{self.previous_pes_packet_crc:X}\n"
