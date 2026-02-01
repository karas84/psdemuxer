from __future__ import annotations

from io import BufferedReader

from typing import TYPE_CHECKING

from psdemuxer.exceptions import InvalidMarkerException

if TYPE_CHECKING:
    from psdemuxer.pack.pes.flagdata import FlagData


class AdditionalCopyInfoFlag:
    def __init__(self, pes_pfd: FlagData, fh: BufferedReader):
        self.pes_pfd: FlagData = pes_pfd
        self.data: bytearray = bytearray(1)

        fh.readinto(self.data)

        if not self.marker_0:
            raise InvalidMarkerException()

    @property
    def marker_0(self) -> int:
        return (self.data[0] & 0b10000000) >> 7

    @property
    def additional_copy_info(self) -> int:
        return (self.data[0] & 0b01111111) >> 0

    def __str__(self) -> str:
        return f"additional_copy_info=0x{self.additional_copy_info:X}\n"
