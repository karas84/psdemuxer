from __future__ import annotations

import os

from io import BufferedReader
from typing import TYPE_CHECKING

from psdemuxer.constants import get_stream_id_by_name as _s
from psdemuxer.pack.pes.flagdata import FlagData
from psdemuxer.utils import peek

if TYPE_CHECKING:
    from psdemuxer.pack import PackStartHeader


class PESPacket:
    pkt_no = 0

    def __init__(self, psh: PackStartHeader, fh: BufferedReader):
        self.no = PESPacket.pkt_no
        self.pos = fh.tell()
        self.psh = psh
        self.data: bytearray = bytearray(6)
        self.flag_data: FlagData | None = None
        self.header_length: int = 0
        self._private_stream_id: int | None = None

        fh.readinto(self.data)
        PESPacket.pkt_no += 1

        self.pes_packet_data_bytes: bytearray | None = None

        pos = fh.tell()

        if (
            self.stream_id != _s("program_stream_map")
            and self.stream_id != _s("padding_stream")
            and self.stream_id != _s("private_stream_2")
            and self.stream_id != _s("ECM_stream")
            and self.stream_id != _s("EMM_stream")
            and self.stream_id != _s("program_stream_directory")
            and self.stream_id != _s("DSMCC_stream")
            and self.stream_id != _s("ISO/Rec. ITU-T H.222.1 type E")
        ):
            self.flag_data = FlagData(self, fh)

            bytes_read = fh.tell() - pos
            self.pes_packet_data_bytes_n = bytes_left = self.pes_packet_length - bytes_read

            self.header_length = fh.tell() - self.pos

            if self.stream_id == _s("private_stream_1"):
                self._private_stream_id = peek(fh, 1)[0]

            # self.pes_packet_data_bytes = bytearray(bytes_left)
            # fh.readinto(self.pes_packet_data_bytes)
            fh.seek(bytes_left, os.SEEK_CUR)
        elif (
            self.stream_id == _s("program_stream_map")
            or self.stream_id == _s("ECM_stream")
            or self.stream_id == _s("EMM_stream")
            or self.stream_id == _s("program_stream_directory")
            or self.stream_id == _s("DSMCC_stream")
            or self.stream_id == _s("ISO/Rec. ITU-T H.222.1 type E")
        ):
            bytes_read = fh.tell() - pos
            self.pes_packet_data_bytes_n = bytes_left = self.pes_packet_length - bytes_read

            self.header_length = fh.tell() - self.pos

            # self.pes_packet_data_bytes = bytearray(bytes_left)
            # fh.readinto(self.pes_packet_data_bytes)
            fh.seek(bytes_left, os.SEEK_CUR)
        elif self.stream_id == _s("padding_stream"):
            self.header_length = fh.tell() - self.pos

            self.pes_packet_data_bytes_n = self.pes_packet_length

            # self.padding_bytes: bytearray = bytearray(self.pes_packet_length)
            # fh.readinto(self.padding_bytes)
            fh.seek(self.pes_packet_length, os.SEEK_CUR)
        else:  # TODO: check this!
            raise RuntimeError("???")

    @property
    def packet_start_code_prefix(self):
        return self.data[:3]

    @property
    def stream_id(self) -> int:
        return self.data[3]

    @property
    def pes_packet_length(self) -> int:
        return (self.data[4]) << 8 | (self.data[5])

    @property
    def pes_full_packet_length(self) -> int:
        return 6 + self.pes_packet_length

    # @property
    # def pes_data_pos(self) -> int:
    #     return self.pos +

    def __str__(self) -> str:
        str_ = f"-- 0x{self.pos:X} PESPacket (#{self.no:6d}) --\n"
        private_stream_id_str = ""
        if self._private_stream_id is not None:
            private_stream_id_str += f"(0x{self._private_stream_id:02X})"
        str_ += (
            f"packet_start_code_prefix=0x{self.packet_start_code_prefix.hex().upper()}\n"
            f"stream_id=0x{self.stream_id:X}{private_stream_id_str}\n"
            f"pes_packet_length=0x{self.pes_packet_length:X} ({self.pes_packet_length})\n"
        )
        if self.flag_data:
            str_ += f"{self.flag_data}"
        if self.stream_id == _s("padding_stream"):
            str_ += f"padding_byte_n=0x{self.pes_packet_data_bytes_n:X} ({self.pes_packet_data_bytes_n})\n"
        else:
            str_ += f"PES_packet_data_byte_n=0x{self.pes_packet_data_bytes_n:X} ({self.pes_packet_data_bytes_n})\n"
        return str_

    def __repr__(self) -> str:
        return f"    {self.no:4d} 0x{self.pos:08X} 0x{self.stream_id:02X}"
