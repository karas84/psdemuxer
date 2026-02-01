from __future__ import annotations

from io import BufferedReader
from typing import TYPE_CHECKING

from psdemuxer.exceptions import InvalidFixedBitsException

if TYPE_CHECKING:
    from psdemuxer.pack.pes.extension import ExtensionFlag


class PSTDBuffer:
    def __init__(self, pes_ef: ExtensionFlag, fh: BufferedReader):
        self.pes_pfd: ExtensionFlag = pes_ef
        self.data: bytearray = bytearray(2)

        fh.readinto(self.data)

        if self.b_01 != 0b01:
            raise InvalidFixedBitsException()

    @property
    def b_01(self) -> int:
        return (self.data[0] & 0b11000000) >> 6

    @property
    def p_std_buffer_scale(self) -> int:
        return (self.data[0] & 0b00100000) >> 5

    @property
    def p_std_buffer_size(self) -> int:
        # fmt: off
        return (((self.data[0] & 0b00011111) >> 0) << 8) | \
               (((self.data[1] & 0b11111111) >> 0) << 0)
        # fmt: on

    def __str__(self) -> str:
        return (
            f"01\n"
            f"P-STD_buffer_scale={self.p_std_buffer_scale}\n"
            f"P-STD_buffer_size=0x{self.p_std_buffer_size:X}\n"
        )
