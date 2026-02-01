from __future__ import annotations

from io import BufferedReader

from typing import TYPE_CHECKING

from psdemuxer.exceptions import InvalidMarkerException

if TYPE_CHECKING:
    from psdemuxer.pack.pes.extension import ExtensionFlag


class ProgramPacketSequenceCounter:
    def __init__(self, pes_ef: ExtensionFlag, fh: BufferedReader):
        self.pes_ef: ExtensionFlag = pes_ef
        self.data: bytearray = bytearray(2)

        fh.readinto(self.data)

        if not self.marker_0 or not self.marker_1:
            raise InvalidMarkerException()

    @property
    def marker_0(self) -> int:
        return (self.data[0] & 0b10000000) >> 7

    @property
    def program_packet_sequence_counter(self) -> int:
        return (self.data[0] & 0b01111111) >> 0

    @property
    def marker_1(self) -> int:
        return (self.data[1] & 0b10000000) >> 7

    @property
    def mpeg1_mpeg2_identifier(self) -> int:
        return (self.data[1] & 0b01000000) >> 6

    @property
    def original_stuff_length(self) -> int:
        return (self.data[1] & 0b00111111) >> 0

    def __str__(self) -> str:
        return (
            f"program_packet_sequence_counter=0x{self.program_packet_sequence_counter:X}\n"
            f"MPEG1_MPEG2_identifier=0b{self.mpeg1_mpeg2_identifier:b}\n"
            f"original_stuff_length=0x{self.original_stuff_length:X}\n"
        )
