from __future__ import annotations

# import os

from io import BufferedReader
from typing import TYPE_CHECKING

from psdemuxer.exceptions import InvalidFixedBitsException
from psdemuxer.pack.pes.copy import AdditionalCopyInfoFlag
from psdemuxer.pack.pes.crc import CRCFlag
from psdemuxer.pack.pes.dms import DMSTrickModeControl
from psdemuxer.pack.pes.escr import FlagESCR
from psdemuxer.pack.pes.esrate import FlagESRate
from psdemuxer.pack.pes.extension import ExtensionFlag
from psdemuxer.pack.pes.ptsdts import FlagPTS, FlagPTSDTS

if TYPE_CHECKING:
    from psdemuxer.pack.pes import PESPacket


class FlagData:
    def __init__(self, pes: PESPacket, fh: BufferedReader):
        self.pes: PESPacket = pes
        self.data: bytearray = bytearray(3)
        self.pes_flag_pts_dts: FlagPTS | FlagPTSDTS | None = None
        self.pes_flag_escr: FlagESCR | None = None
        self.pes_flag_es_rate: FlagESRate | None = None
        self.pes_dms_trick_mode_control: DMSTrickModeControl | None = None
        self.pes_additional_copy_info_flag: AdditionalCopyInfoFlag | None = None
        self.pes_crc_flag_obj: CRCFlag | None = None
        self.pes_extension: ExtensionFlag | None = None

        fh.readinto(self.data)

        if self.b_10 != 0b10:
            raise InvalidFixedBitsException()

        pos = fh.tell()

        if self.pts_dts_flags == 0b10:
            self.pes_flag_pts_dts = FlagPTS(self, fh)

        if self.pts_dts_flags == 0b11:
            self.pes_flag_pts_dts = FlagPTSDTS(self, fh)

        if self.escr_flag == 0b1:
            self.pes_flag_escr = FlagESCR(self, fh)

        if self.es_rate_flag == 0b1:
            self.pes_flag_es_rate = FlagESRate(self, fh)

        if self.dsm_trick_mode_flag == 0b1:
            self.pes_dms_trick_mode_control = DMSTrickModeControl(self, fh)

        if self.additional_copy_info_flag == 0b1:
            self.pes_additional_copy_info_flag = AdditionalCopyInfoFlag(self, fh)

        if self.pes_crc_flag == 0x1:
            self.pes_crc_flag_obj = CRCFlag(self, fh)

        if self.pes_extension_flag == 0b1:
            self.pes_extension = ExtensionFlag(self, fh)

        bytes_read = fh.tell() - pos
        bytes_left = self.pes_header_data_length - bytes_read

        assert bytes_left >= 0

        # self.stuffing_byte: bytearray = bytearray(bytes_left)
        # fh.readinto(self.stuffing_byte)
        # fh.seek(bytes_left, os.SEEK_CUR)
        self.stuffing_bytes = fh.read(bytes_left)
        assert len(self.stuffing_bytes) == bytes_left
        assert self.stuffing_bytes == (b"\xFF" * bytes_left)

    def __str__(self) -> str:
        str_ = (
            f"10\n"
            f"PES_scrambling_control={self.pes_scrambling_control}\n"
            f"PES_priority={self.pes_priority}\n"
            f"data_alignment_indicator={self.data_alignment_indicator}\n"
            f"copyright={self.copyright}\n"
            f"original_or_copy={self.original_or_copy}\n"
            f"PTS_DTS_flags=0b{self.pts_dts_flags:b}\n"
            f"ESCR_flag={self.escr_flag}\n"
            f"ES_rate_flag={self.es_rate_flag}\n"
            f"DSM_trick_mode_flag={self.dsm_trick_mode_flag}\n"
            f"additional_copy_info_flag={self.additional_copy_info_flag}\n"
            f"PES_CRC_flag={self.pes_crc_flag}\n"
            f"PES_extension_flag={self.pes_extension_flag}\n"
            f"PES_header_data_length=0x{self.pes_header_data_length:X} ({self.pes_header_data_length})\n"
        )
        if self.pes_flag_pts_dts:
            str_ += f"{self.pes_flag_pts_dts}"
        if self.pes_flag_escr:
            str_ += f"{self.pes_flag_escr}"
        if self.pes_flag_es_rate:
            str_ += f"{self.pes_flag_es_rate}"
        if self.pes_dms_trick_mode_control:
            str_ += f"{self.pes_dms_trick_mode_control}"
        if self.pes_additional_copy_info_flag:
            str_ += f"{self.pes_additional_copy_info_flag}"
        if self.pes_crc_flag_obj:
            str_ += f"{self.pes_crc_flag_obj}"
        if self.pes_extension:
            str_ += f"{self.pes_extension}"
        if self.stuffing_bytes:
            str_ += f"stuffing_byte({len(self.stuffing_bytes)})=0x{self.stuffing_bytes.hex().upper()}\n"
        return str_

    @property
    def b_10(self) -> int:
        return (self.data[0] & 0b11000000) >> 6

    @property
    def pes_scrambling_control(self) -> int:
        return (self.data[0] & 0b00110000) >> 4

    @property
    def pes_priority(self) -> int:
        return (self.data[0] & 0b00001000) >> 3

    @property
    def data_alignment_indicator(self) -> int:
        return (self.data[0] & 0b00000100) >> 2

    @property
    def copyright(self) -> int:
        return (self.data[0] & 0b00000010) >> 1

    @property
    def original_or_copy(self) -> int:
        return (self.data[0] & 0b00000001) >> 0

    @property
    def pts_dts_flags(self) -> int:
        return (self.data[1] & 0b11000000) >> 6

    @property
    def escr_flag(self) -> int:
        return (self.data[1] & 0b00100000) >> 5

    @property
    def es_rate_flag(self) -> int:
        return (self.data[1] & 0b00010000) >> 4

    @property
    def dsm_trick_mode_flag(self) -> int:
        return (self.data[1] & 0b00001000) >> 3

    @property
    def additional_copy_info_flag(self) -> int:
        return (self.data[1] & 0b00000100) >> 2

    @property
    def pes_crc_flag(self) -> int:
        return (self.data[1] & 0b00000010) >> 1

    @property
    def pes_extension_flag(self) -> int:
        return (self.data[1] & 0b00000001) >> 0

    @property
    def pes_header_data_length(self) -> int:
        return (self.data[2] & 0b11111111) >> 0
