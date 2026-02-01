from __future__ import annotations

from io import BufferedReader

from psdemuxer.utils import peek
from psdemuxer.pack.pes import PESPacket
from psdemuxer.constants import system_header_start_code, packet_start_code_prefix, program_end_code
from psdemuxer.exceptions import InvalidFixedBitsException, InvalidMarkerException
from psdemuxer.pack.system import SystemHeader


class PackStartHeader:
    start_code = b"\x00\x00\x01\xba"
    size = 14

    def __len__(self) -> int:
        return len(self.pes_list)

    def __init__(self, fh: BufferedReader):
        self.pos = fh.tell()
        self.data: bytearray = bytearray(PackStartHeader.size)
        self.system_header: SystemHeader | None = None
        self.pes_list: list[PESPacket] = []

        fh.readinto(self.data)

        if self.b_01 != 0b01:
            raise InvalidFixedBitsException("not an MPEG-2 PS Stream")

        if (
            not self.marker_0
            or not self.marker_1
            or not self.marker_2
            or not self.marker_3
            or not self.marker_4
            or not self.marker_5
        ):
            raise InvalidMarkerException("invalid markers")

        if self.header != PackStartHeader.start_code:  # type: ignore
            assert self.header == PackStartHeader.start_code
        fh.read(self.pack_stuffing_length)

        next_bits = peek(fh, 4)

        if next_bits == system_header_start_code:
            self.system_header = SystemHeader(fh)

        next_bits = peek(fh, 4)

        while next_bits[:3] == packet_start_code_prefix:
            if next_bits == PackStartHeader.start_code:
                break

            if next_bits == program_end_code:
                break

            pes = PESPacket(self, fh)
            self.pes_list.append(pes)
            # print(pes)

            next_bits = peek(fh, 4)

        # print(repr(self))
        # for pes in self.pes_list:
        #     print(repr(pes))

    @property
    def header(self):
        return self.data[:4]

    @property
    def b_01(self) -> int:
        return (self.data[4] & 0b11000000) >> 6

    @property
    def marker_0(self) -> int:
        return (self.data[4] & 0b00000100) >> 2

    @property
    def marker_1(self) -> int:
        return (self.data[6] & 0b00000100) >> 2

    @property
    def marker_2(self) -> int:
        return (self.data[8] & 0b00000100) >> 2

    @property
    def marker_3(self) -> int:
        return (self.data[9] & 0b00000001) >> 0

    @property
    def marker_4(self) -> int:
        return (self.data[12] & 0b00000010) >> 1

    @property
    def marker_5(self) -> int:
        return (self.data[12] & 0b00000001) >> 0

    @property
    def scr(self) -> int:
        # fmt: off
        return \
            ((self.data[4] & 0b00111000) >> 3) << 30 | \
            ((self.data[4] & 0b00000011) >> 0) << 28 | \
            ((self.data[5] & 0b11111111) >> 0) << 20 | \
            ((self.data[6] & 0b11111000) >> 3) << 15 | \
            ((self.data[6] & 0b00000011) >> 0) << 13 | \
            ((self.data[7] & 0b11111111) >> 0) << 5 | \
            ((self.data[8] & 0b11111000) >> 3) << 0
        # fmt: on

    @property
    def scr_ext(self) -> int:
        # fmt: off
        return \
            ((self.data[8] & 0b00000011) >> 0) << 7 | \
            ((self.data[9] & 0b11111110) >> 1) << 0
        # fmt: on

    @property
    def system_clock_reference(self) -> int:
        return 300 * self.scr + self.scr_ext

    @property
    def program_mux_rate(self) -> int:
        # fmt: off
        return  (50 * 8) * ( \
            ((self.data[10] & 0b11111111) >> 0) << 14 | \
            ((self.data[11] & 0b11111111) >> 0) << 6 | \
            ((self.data[12] & 0b11111100) >> 2) << 0)
        # fmt: on

    @property
    def reserved(self) -> int:
        return (self.data[13] & 0b11111000) >> 3

    @property
    def pack_stuffing_length(self) -> int:
        return (self.data[13] & 0b00000111) >> 0

    def __str__(self) -> str:
        str_ = f"-- 0x{self.pos:X} PackStartHeader --\n"
        str_ += "\n".join(
            [
                f"header=0x{self.header.hex().upper()}",
                f"system_clock_reference={self.system_clock_reference}",
                f"program_mux_rate={self.program_mux_rate}",
                f"pack_stuffing_length={self.pack_stuffing_length}",
            ]
        )
        if self.system_header:
            str_ += "\n" + str(self.system_header)
        return str_

    def __repr__(self) -> str:
        ws = "*" if self.system_header else " "
        return f"SH{ws} 0x{self.pos:08X} 0x{self.header[-1]:02X}"
