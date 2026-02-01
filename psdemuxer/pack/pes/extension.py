from __future__ import annotations

import os

from io import BufferedReader
from typing import TYPE_CHECKING

from psdemuxer.exceptions import InvalidMarkerException
from psdemuxer.pack.pes.stdbuf import PSTDBuffer
from psdemuxer.pack.pes.sequence import ProgramPacketSequenceCounter


if TYPE_CHECKING:
    from psdemuxer.pack.pes import FlagData


class StreamIdExtensionReserved:
    def __init__(self, pes_e2: Extension2, data: bytearray, fh: BufferedReader):
        self.pes_e2: Extension2 = pes_e2
        self.data: bytearray = data
        self._tref_extension: TrefExtension | None = None

        if self.tref_extension_flag == 0b0:
            self._tref_extension = TrefExtension(self, fh)

    @property
    def reserved(self) -> int:
        return (self.data[1] & 0b01111110) >> 1

    @property
    def tref_extension_flag(self) -> int:
        return (self.data[1] & 0b00000001) >> 0

    def __str__(self) -> str:
        # fmt: off
        str_ = (
            f"reserved=0x{self.reserved:X}\n"
            f"tref_extension_flag={self.tref_extension_flag}\n"
        )
        # fmt: on
        if self._tref_extension:
            str_ += f"{self._tref_extension}"
        return str_


class StreamIdExtension:
    def __init__(self, pes_e2: Extension2, data: bytearray):
        self.pes_e2: Extension2 = pes_e2
        self.data: bytearray = data

    @property
    def stream_id_extension(self) -> int:
        return (self.data[1] & 0b01111111) >> 0

    def __str__(self) -> str:
        return f"stream_id_extension=0x{self.stream_id_extension:X}\n"


class Extension2:
    def __init__(self, pes_ef: ExtensionFlag, fh: BufferedReader):
        self.pes_pfd: ExtensionFlag = pes_ef
        self.data: bytearray = bytearray(2)
        self._stream_id_extension: StreamIdExtension | None = None
        self._stream_id_extension_reserved: StreamIdExtensionReserved | None = None

        fh.readinto(self.data)

        if not self.marker_0:
            raise InvalidMarkerException()

        self._n3: int = 0
        self._reserved = bytearray(0)

        if self.stream_id_extension_flag == 0b0:
            self._stream_id_extension = StreamIdExtension(self, self.data)
        else:
            self._stream_id_extension_reserved = StreamIdExtensionReserved(self, self.data, fh)
            if self._stream_id_extension_reserved.tref_extension_flag == 0b0:
                self._n3 = 5

        if self._n3 > 0:
            # self._reserved = bytearray(self._n3)
            # fh.readinto(self._reserved)
            fh.seek(self._n3, os.SEEK_CUR)

    @property
    def marker_0(self) -> int:
        return (self.data[0] & 0b10000000) >> 7

    @property
    def pes_extension_field_length(self) -> int:
        return (self.data[0] & 0b01111111) >> 0

    @property
    def stream_id_extension_flag(self) -> int:
        return (self.data[1] & 0b10000000) >> 7

    def __str__(self) -> str:
        str_ = (
            f"PES_extension_field_length={self.pes_extension_field_length}\n"
            f"stream_id_extension_flag={self.stream_id_extension_flag}\n"
        )
        if self._stream_id_extension:
            str_ += f"{self._stream_id_extension}"
        if self._stream_id_extension_reserved:
            str_ += f"{self._stream_id_extension_reserved}"
        return str_


class TrefExtension:
    def __init__(self, pes_res: StreamIdExtensionReserved, fh: BufferedReader):
        self.pes_res: StreamIdExtensionReserved = pes_res
        self.data: bytearray = bytearray(5)

        fh.readinto(self.data)

        if not self.marker_0 or not self.marker_1 or not self.marker_2:
            raise InvalidMarkerException()

    @property
    def reserved(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def marker_0(self) -> int:
        return (self.data[0] & 0b00000001) >> 0

    @property
    def marker_1(self) -> int:
        return (self.data[2] & 0b00000001) >> 0

    @property
    def marker_2(self) -> int:
        return (self.data[4] & 0b00000001) >> 0

    @property
    def tref(self) -> int:
        # fmt: off
        return (((self.data[0] & 0b00001110) >> 1) << 30) | \
               (((self.data[1] & 0b11111111) >> 0) << 22) | \
               (((self.data[2] & 0b11111110) >> 1) << 15) | \
               (((self.data[3] & 0b11111111) >> 0) <<  7) | \
               (((self.data[4] & 0b11111110) >> 1) <<  0)
        # fmt: on

    def __str__(self) -> str:
        # fmt: off
        return (
            f"reserved=0x{self.reserved:X}\n"
            f"TREF=0x{self.tref:X}\n"
        )

    # fmt: on


class PrivateData:
    def __init__(self, pes_pfd: ExtensionFlag, fh: BufferedReader):
        self.pes_ef: ExtensionFlag = pes_pfd
        self.data: bytearray = bytearray(16)

        fh.readinto(self.data)

    @property
    def pes_private_data(self) -> bytearray:
        return self.data

    def __str__(self) -> str:
        return f"PES_private_data=0x{self.pes_private_data.hex().upper()}\n"


class ExtensionFlag:
    def __init__(self, pes_pfd: FlagData, fh: BufferedReader):
        self.pes_pfd: FlagData = pes_pfd
        self.data: bytearray = bytearray(1)
        self._private_data: PrivateData | None = None
        self._program_packet_sequence_counter: ProgramPacketSequenceCounter | None = None
        self._p_std_buffer: PSTDBuffer | None = None
        self._extension_2: Extension2 | None = None

        fh.readinto(self.data)

        if self.pes_private_data_flag == 0x1:
            self._private_data = PrivateData(self, fh)

        assert self.pack_header_field_flag == 0b0

        if self.program_packet_sequence_counter_flag == 0b1:
            self._program_packet_sequence_counter = ProgramPacketSequenceCounter(self, fh)

        if self.p_std_buffer_flag == 0b1:
            self._p_std_buffer = PSTDBuffer(self, fh)

        if self.pes_extension_flag_2 == 0b1:
            self._extension_2 = Extension2(self, fh)

    @property
    def pes_private_data_flag(self) -> int:
        return (self.data[0] & 0b10000000) >> 7

    @property
    def pack_header_field_flag(self) -> int:
        return (self.data[0] & 0b01000000) >> 6

    @property
    def program_packet_sequence_counter_flag(self) -> int:
        return (self.data[0] & 0b00100000) >> 5

    @property
    def p_std_buffer_flag(self) -> int:
        return (self.data[0] & 0b00010000) >> 4

    @property
    def reserved(self) -> int:
        return (self.data[0] & 0b00001110) >> 1

    @property
    def pes_extension_flag_2(self) -> int:
        return (self.data[0] & 0b0000001) >> 0

    def __str__(self) -> str:
        srt_ = (
            f"PES_private_data_flag={self.pes_private_data_flag}\n"
            f"pack_header_field_flag={self.pack_header_field_flag}\n"
            f"program_packet_sequence_counter_flag={self.program_packet_sequence_counter_flag}\n"
            f"P-STD_buffer_flag={self.p_std_buffer_flag}\n"
            f"reserved=0b{self.reserved:b}\n"
            f"PES_extension_flag_2={self.pes_extension_flag_2:b}\n"
        )
        if self._private_data:
            srt_ += f"{self._private_data}"
        if self._program_packet_sequence_counter:
            srt_ += f"{self._program_packet_sequence_counter}"
        if self._p_std_buffer:
            srt_ += f"{self._p_std_buffer}"
        if self._extension_2:
            srt_ += f"{self._extension_2}"
        return srt_
