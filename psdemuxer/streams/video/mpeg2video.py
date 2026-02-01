from __future__ import annotations

from io import BufferedReader
from enum import Enum
from functools import lru_cache
import os

from psdemuxer.utils import bytearray_append, bytearray_extend, bytearray_resize, next_start_code, peek
from psdemuxer.io.bits import BitStreamReader
from psdemuxer.constants import start_code_prefix
from psdemuxer.exceptions import InvalidMarkerException, MPEG2FileFormatException


aspect_ratio_information_map = {
    0b0000: "forbidden",
    0b0001: "1:1",
    0b0010: "4:3",
    0b0011: "16:9",
    0b0100: "2.21:1",
    0b0101: "reserved",
    0b0110: "reserved",
    0b0111: "reserved",
    0b1000: "reserved",
    0b1001: "reserved",
    0b1010: "reserved",
    0b1011: "reserved",
    0b1100: "reserved",
    0b1101: "reserved",
    0b1110: "reserved",
    0b1111: "reserved",
}

frame_rate_map = {
    0b0000: "forbidden",
    0b0001: "23.976",
    0b0010: "24",
    0b0011: "25",
    0b0100: "29.97",
    0b0101: "30",
    0b0110: "50",
    0b0111: "59.94",
    0b1000: "60",
    0b1001: "reserved",
    0b1010: "reserved",
    0b1011: "reserved",
    0b1100: "reserved",
    0b1101: "reserved",
    0b1110: "reserved",
    0b1111: "reserved",
}

chroma_format_map = {
    0b00: "reserved",
    0b01: "4:2:0",
    0b10: "4:2:2",
    0b11: "4:4:4",
}


picture_start_code = b"\x00\x00\x01\x00"
user_data_start_code = b"\x00\x00\x01\xb2"
sequence_header_code = b"\x00\x00\x01\xb3"
sequence_error_code = b"\x00\x00\x01\xb4"
extension_start_code = b"\x00\x00\x01\xb5"
sequence_end_code = b"\x00\x00\x01\xb7"
group_start_code = b"\x00\x00\x01\xb8"


def is_slice_start_code(code: bytes):
    return len(code) == 4 and code[:3] == b"\x00\x00\x01" and 0x01 <= code[3] <= 0xAF


start_code_map = {
    "picture_start_code": 0x00,
    "reserved": 0xB0,
    "reserved": 0xB1,
    "user_data_start_code": 0xB2,
    "sequence_header_code": 0xB3,
    "sequence_error_code": 0xB4,
    "extension_start_code": 0xB5,
    "reserved": 0xB6,
    "sequence_end_code": 0xB7,
    "group_start_code": 0xB8,
}


picture_coding_type_map = {
    0b000: "forbidden",
    0b001: "intra-coded (I)",
    0b010: "predictive-coded (P)",
    0b011: "bidirectionally-predictive-coded (B)",
    0b100: "shall not be used",
    0b101: "reserved",
    0b110: "reserved",
    0b111: "reserved",
}


class PictureCodingType(int, Enum):
    I = 1
    P = 2
    B = 3


@lru_cache(maxsize=256)
def is_start_code(code: int, name: str):
    if 0x01 <= code <= 0xAF:
        return name == "slice_start_code"

    if 0xB9 <= code <= 0xFF:
        return False

    start_code = start_code_map.get(name, None)

    if start_code is None:
        return False

    return start_code == code


extension_start_code_identifier = {
    0b0000: "reserved",
    0b0001: "Sequence Extension ID",
    0b0010: "Sequence Display Extension ID",
    0b0011: "Quant Matrix Extension ID",
    0b0100: "Copyright Extension ID",
    0b0101: "Sequence Scalable Extension ID",
    0b0110: "reserved",
    0b0111: "Picture Display Extension ID",
    0b1000: "Picture Coding Extension ID",
    0b1001: "Picture Spatial Scalable Extension ID",
    0b1010: "Picture Temporal Scalable Extension ID",
    0b1011: "reserved",
    0b1100: "reserved",
    0b1101: "reserved",
    0b1110: "reserved",
    0b1111: "reserved",
}


@lru_cache(16)
def get_extension_start_code_identifier(code_name: str):
    for code, name in extension_start_code_identifier.items():
        if code_name == name:
            return code
    return None


_c = get_extension_start_code_identifier


class SequenceExtension:
    def __init__(self, seq: Sequence, fh: BufferedReader, is_first: bool = True):
        self.seq = seq

        self.data: bytearray = bytearray(10)
        fh.readinto(self.data)

        self.seq.progressive_sequence = self.progressive_sequence

        next_start_code(fh)

    @property
    def extension_start_code(self) -> bytes:
        return self.data[:4]

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[4] & 0b11110000) >> 4

    @property
    def profile_and_level_indication(self) -> int:
        # fmt: off
        return \
            ((self.data[4] & 0b00001111) >> 0) << 4 | \
            ((self.data[5] & 0b11110000) >> 4) << 0
        # fmt: on

    @property
    def progressive_sequence(self) -> int:
        return (self.data[5] & 0b00001000) >> 3

    @property
    def chroma_format(self) -> int:
        return (self.data[5] & 0b00000110) >> 1

    @property
    def horizontal_size_extension(self) -> int:
        # fmt: off
        return \
            ((self.data[5] & 0b00000001) >> 0) << 1 | \
            ((self.data[6] & 0b10000000) >> 7) << 0
        # fmt: on

    @property
    def vertical_size_extension(self) -> int:
        return (self.data[6] & 0b01100000) >> 5

    @property
    def bit_rate_extension(self) -> int:
        # fmt: off
        return \
            ((self.data[6] & 0b00011111) >> 7) << 1 | \
            ((self.data[7] & 0b11111110) >> 1) << 0
        # fmt: on

    @property
    def marker_0(self) -> int:
        return (self.data[7] & 0b00000001) >> 0

    @property
    def vbv_buffer_size_extension(self) -> int:
        return (self.data[8] & 0b11111111) >> 0
        # fmt: on

    @property
    def frame_rate_extension_n(self) -> int:
        return (self.data[9] & 0b01100000) >> 5
        # fmt: on

    @property
    def frame_rate_extension_d(self) -> int:
        return (self.data[9] & 0b00011111) >> 0

    def __str__(self) -> str:
        return (
            f"extension_start_code=0x{self.extension_start_code.hex().upper()}\n"
            f"extension_start_code_identifier=0x{self.extension_start_code_identifier:X}\n"
            f"profile_and_level_indication=0x{self.profile_and_level_indication:X}\n"
            f"progressive_sequence=0x{self.progressive_sequence:X}\n"
            f"chroma_format=0x{self.chroma_format:X}\n"
            f"horizontal_size_extension=0x{self.horizontal_size_extension:X}\n"
            f"vertical_size_extension=0x{self.vertical_size_extension:X}\n"
            f"bit_rate_extension=0x{self.bit_rate_extension:X}\n"
            f"bit_rate_extension=0x{self.bit_rate_extension:X}\n"
            f"vbv_buffer_size_extension=0x{self.vbv_buffer_size_extension:X}\n"
            f"frame_rate_extension_n=0x{self.frame_rate_extension_n:X}\n"
            f"frame_rate_extension_d=0x{self.frame_rate_extension_d:X}\n"
        )


class SequenceHeader:
    def __init__(self, seq: Sequence, fh: BufferedReader):
        self.seq = seq

        self.data: bytearray = bytearray(12)
        fh.readinto(self.data)

        assert self.sequence_header_code == sequence_header_code, self.sequence_header_code.hex()
        assert self.marker_bit == 0b1

        if self.load_intra_quantiser_matrix:
            self.data = bytearray_resize(self.data, 64)

        if self.load_non_intra_quantiser_matrix:
            self.data = bytearray_resize(self.data, 64)

    @property
    def sequence_header_code(self) -> bytes:
        return self.data[:4]

    @property
    def horizontal_size_value(self) -> int:
        # fmt: off
        return \
            ((self.data[4] & 0b11111111) >> 0) << 4 | \
            ((self.data[5] & 0b11110000) >> 4) << 0
        # fmt: on

    @property
    def vertical_size_value(self) -> int:
        # fmt: off
        return \
            ((self.data[5] & 0b00001111) >> 0) << 8 | \
            ((self.data[6] & 0b11111111) >> 0) << 0
        # fmt: on

    @property
    def aspect_ratio_information(self) -> int:
        return (self.data[7] & 0b11110000) >> 4

    @property
    def frame_rate_code(self) -> int:
        return (self.data[7] & 0b00001111) >> 0

    @property
    def bit_rate_value(self) -> int:
        # fmt: off
        return \
            ((self.data[8]  & 0b11111111) >> 0) << 10 | \
            ((self.data[9]  & 0b11111111) >> 0) <<  2 | \
            ((self.data[10] & 0b11000000) >> 6) <<  0
        # fmt: on

    @property
    def marker_bit(self) -> int:
        return (self.data[10] & 0b00100000) >> 5

    @property
    def vbv_buffer_size_value(self) -> int:
        # fmt: off
        return \
            ((self.data[10] & 0b00011111) >> 0) << 5 | \
            ((self.data[11] & 0b11111000) >> 3) << 0
        # fmt: on

    @property
    def constrained_parameters_flag(self) -> int:
        return (self.data[11] & 0b00000100) >> 2

    @property
    def load_intra_quantiser_matrix(self) -> int:
        return (self.data[11] & 0b00000010) >> 1

    @property
    def intra_quantiser_matrix(self) -> bytes | None:
        if not self.load_intra_quantiser_matrix:
            return None

        intra_quantiser_matrix_ = bytearray(64)
        for i in range(64):
            # fmt: off
            intra_quantiser_matrix_[i] = \
                ((self.data[11 + i + 0] & 0b00000001) >> 0) << 7 | \
                ((self.data[11 + i + 1] & 0b11111110) >> 1) << 0
            # fmt: on
        return intra_quantiser_matrix_

    @property
    def load_non_intra_quantiser_matrix(self) -> int:
        n = len(self.data) - 1
        return (self.data[n] & 0b00000001) >> 0

    @property
    def non_intra_quantiser_matrix(self) -> bytes | None:
        n = len(self.data) - 0
        return self.data[n : n + 64]

    def __str__(self) -> str:
        ar_str = aspect_ratio_information_map.get(self.aspect_ratio_information)
        fr_str = frame_rate_map.get(self.frame_rate_code)
        return (
            f"sequence_header_code=0x{self.sequence_header_code.hex().upper()}\n"
            f"horizontal_size_value={self.horizontal_size_value}\n"
            f"vertical_size_value={self.vertical_size_value}\n"
            f"aspect_ratio_information={self.aspect_ratio_information} ({ar_str})\n"
            f"frame_rate_code={self.frame_rate_code} ({fr_str} fps)\n"
            f"load_intra_quantiser_matrix={self.load_intra_quantiser_matrix}\n"
            f"load_non_intra_quantiser_matrix={self.load_non_intra_quantiser_matrix}\n"
        )


class SequenceDisplayExtension:
    def __init__(self, ed: ExtensionData, fh: BufferedReader):
        self.ed = ed

        self.data: bytearray = bytearray(1)
        fh.readinto(self.data)

        if self.colour_description:
            self.data = bytearray_extend(self.data, 3)

        if not self.marker_bit_0:
            raise InvalidMarkerException("invalid marker")

        next_start_code(fh)

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def video_format(self) -> int:
        return (self.data[0] & 0b00001110) >> 1

    @property
    def colour_description(self) -> int:
        return (self.data[0] & 0b00000001) >> 0

    @property
    def colour_primaries(self) -> int:
        return self.data[1]

    @property
    def transfer_characteristics(self) -> int:
        return self.data[2]

    @property
    def matrix_coefficients(self) -> int:
        return self.data[2]

    @property
    def display_horizontal_size(self) -> int:
        i = 3 if self.colour_description else 1
        # fmt: off
        return \
            ((self.data[i + 0] & 0b11111111) >> 0) << 6 | \
            ((self.data[i + 1] & 0b11111100) >> 2) << 0
        # fmr: on

    @property
    def marker_bit_0(self) -> int:
        i = 3 if self.colour_description else 1
        return (self.data[i + 1] & 0b00000010) >> 1

    @property
    def display_vertical_size(self) -> int:
        i = 3 if self.colour_description else 1
        # fmt: off
        return \
            ((self.data[i + 1] & 0b00000001) >> 0) << 13 | \
            ((self.data[i + 2] & 0b11111111) >> 0) <<  5 | \
            ((self.data[i + 3] & 0b11111000) >> 3) <<  0
        # fmr: on


class ScalableMode(int, Enum):
    data_partitioning = 0b00
    spatial_scalability = 0b01
    snr_scalability = 0b10
    temporal_scalability = 0b11


class SpatialScalabilityMode:
    def __init__(self, sce: SequenceScalableExtension, fh: BufferedReader):
        self.sce = sce

        self.data: bytearray = bytearray(7)
        fh.readinto(self.data)

    @property
    def lower_layer_prediction_horizontal_size(self) -> int:
        # fmt: off
        return \
            ((self.data[0] & 0b00111111) >> 0) << 8 | \
            ((self.data[1] & 0b11111111) >> 0) << 0
        # fmr: on

    @property
    def marker_bit_0(self) -> int:
        return (self.data[2] & 0b10000000) >> 7

    @property
    def lower_layer_prediction_vertical_size(self) -> int:
        # fmt: off
        return \
            ((self.data[2] & 0b01111111) >> 0) << 7 | \
            ((self.data[3] & 0b11111110) >> 1) << 0
        # fmr: on

    @property
    def horizontal_subsampling_factor_m(self) -> int:
        # fmt: off
        return \
            ((self.data[3] & 0b00000001) >> 0) << 4 | \
            ((self.data[4] & 0b11110000) >> 4) << 0
        # fmr: on

    @property
    def horizontal_subsampling_factor_n(self) -> int:
        # fmt: off
        return \
            ((self.data[4] & 0b00001111) >> 0) << 1 | \
            ((self.data[5] & 0b10000000) >> 7) << 0
        # fmr: on

    @property
    def vertical_subsampling_factor_m(self) -> int:
        return (self.data[5] & 0b011111110) >> 1

    @property
    def vertical_subsampling_factor_n(self) -> int:
        # fmt: off
        return \
            ((self.data[5] & 0b00000001) >> 0) << 4 | \
            ((self.data[6] & 0b11110000) >> 4) << 0
        # fmr: on


class TemporalScalabilityMode:
    def __init__(self, sce: SequenceScalableExtension, fh: BufferedReader):
        self.sce = sce

        self.data: bytearray = bytearray(2)
        fh.readinto(self.data)

    @property
    def picture_mux_enable(self) -> int:
        return (self.data[0] & 0b00100000) >> 5

    @property
    def mux_to_progressive_sequence(self) -> int | None:
        if self.picture_mux_enable:
            return (self.data[1] & 0b00010000) >> 4
        return None

    @property
    def picture_mux_order(self) -> int:
        if self.picture_mux_enable:
            return (self.data[0] & 0b00001110) >> 1
        else:
            return (self.data[0] & 0b00011100) >> 2

    @property
    def picture_mux_factor(self) -> int:
        if self.picture_mux_enable:
            # fmt: off
            return \
                ((self.data[0] & 0b00000001) >> 0) << 2 | \
                ((self.data[1] & 0b11000000) >> 6) << 0
            # fmr: on
        else:
            # fmt: off
            return \
                ((self.data[0] & 0b00000011) >> 0) << 1 | \
                ((self.data[1] & 0b10000000) >> 7) << 0
            # fmr: on


class SequenceScalableExtension:
    def __init__(self, ed: ExtensionData, fh: BufferedReader):
        self.ed = ed
        self.spatial_scalability_mode: SpatialScalabilityMode | None = None
        self.temporal_scalability_mode: TemporalScalabilityMode | None = None

        self.data: bytearray = bytearray(2)
        fh.readinto(self.data)

        if self.scalable_mode == ScalableMode.spatial_scalability:
            fh.seek(fh.tell() - 1)
            self.spatial_scalability_mode = SpatialScalabilityMode(self, fh)

        if self.scalable_mode == ScalableMode.temporal_scalability:
            fh.seek(fh.tell() - 1)
            self.temporal_scalability_mode = TemporalScalabilityMode(self, fh)

        next_start_code(fh)

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def scalable_mode(self) -> int:
        return (self.data[0] & 0b00001100) >> 2

    @property
    def layer_id(self) -> int:
        # fmt: off
        return \
            ((self.data[0] & 0b00000011) >> 0) << 2 | \
            ((self.data[1] & 0b11000000) >> 6) << 0
        # fmr: on


class QuantMatrixExtension:
    def __init__(self, ed: ExtensionData, fh: BufferedReader):
        self.ed = ed

        self.data: bytearray = bytearray(1)
        fh.readinto(self.data)

        if self.load_intra_quantiser_matrix:
            self.data = bytearray_resize(self.data, 64)

        if self.load_non_intra_quantiser_matrix:
            self.data = bytearray_resize(self.data, 64)

        if self.load_chroma_intra_quantiser_matrix:
            self.data = bytearray_resize(self.data, 64)

        if self.load_chroma_non_intra_quantiser_matrix:
            self.data = bytearray_resize(self.data, 64)

        next_start_code(fh)

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def load_intra_quantiser_matrix(self) -> int:
        return (self.data[0] & 0b00001000) >> 3

    @property
    def intra_quantiser_matrix(self) -> bytes | None:
        if not self.load_intra_quantiser_matrix:
            return None

        intra_quantiser_matrix_ = bytearray(64)
        for i in range(64):
            # fmt: off
            intra_quantiser_matrix_[i] = \
                ((self.data[11 + i + 0] & 0b00000111) >> 0) << 5 | \
                ((self.data[11 + i + 1] & 0b11111000) >> 3) << 0
            # fmt: on
        return intra_quantiser_matrix_

    @property
    def load_non_intra_quantiser_matrix(self) -> int:
        n = len(self.data) - 1
        return (self.data[n] & 0b00000100) >> 2

    @property
    def non_intra_quantiser_matrix(self) -> bytes | None:
        if not self.load_non_intra_quantiser_matrix:
            return None

        non_intra_quantiser_matrix_ = bytearray(64)
        n = len(self.data) - 1
        for i in range(64):
            # fmt: off
            non_intra_quantiser_matrix_[i] = \
                ((self.data[n + i + 0] & 0b00000011) >> 0) << 6 | \
                ((self.data[n + i + 1] & 0b11111100) >> 2) << 0
            # fmt: on
        return non_intra_quantiser_matrix_

    @property
    def load_chroma_intra_quantiser_matrix(self) -> int:
        n = len(self.data) - 1
        return (self.data[n] & 0b00000010) >> 1

    @property
    def chroma_intra_quantiser_matrix(self) -> bytes | None:
        if not self.load_chroma_intra_quantiser_matrix:
            return None

        chroma_intra_quantiser_matrix_ = bytearray(64)
        n = len(self.data) - 1
        for i in range(64):
            # fmt: off
            chroma_intra_quantiser_matrix_[i] = \
                ((self.data[n + i + 0] & 0b00000001) >> 0) << 7 | \
                ((self.data[n + i + 1] & 0b11111110) >> 1) << 0
            # fmt: on
        return chroma_intra_quantiser_matrix_

    @property
    def load_chroma_non_intra_quantiser_matrix(self) -> int:
        n = len(self.data) - 1
        return (self.data[n] & 0b00000001) >> 0

    @property
    def chroma_non_intra_quantiser_matrix(self) -> bytes | None:
        if not self.load_chroma_non_intra_quantiser_matrix:
            return None

        n = len(self.data) - 1
        return self.data[n : n + 64]


class CopyrightExtension:
    def __init__(self, ed: ExtensionData, fh: BufferedReader):
        self.ed = ed

        self.data: bytearray = bytearray(11)
        fh.readinto(self.data)

        if not self.marker_bit_0 or not self.marker_bit_1 or not self.marker_bit_2:
            raise InvalidMarkerException("invalid marker")

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def copyright_flag(self) -> int:
        return (self.data[0] & 0b00001000) >> 3

    @property
    def copyright_identifier(self) -> int:
        # fmt: off
        return \
            (((self.data[0] & 0b00000111) >> 0) << 5) | \
            (((self.data[1] & 0b11111000) >> 3) << 0)
        # fmt: on

    @property
    def original_or_copy(self) -> int:
        return (self.data[1] & 0b00000100) >> 2

    @property
    def reserved(self) -> int:
        # fmt: off
        return \
            (((self.data[1] & 0b00000011) >> 0) << 5) | \
            (((self.data[2] & 0b11111000) >> 3) << 0)
        # fmt: on

    @property
    def marker_bit_0(self) -> int:
        return (self.data[2] & 0b00000100) >> 2

    @property
    def copyright_number_1(self) -> int:
        # fmt: off
        return \
            (((self.data[2] & 0b00000011) >> 0) << 18) | \
            (((self.data[3] & 0b11111111) >> 0) << 10) | \
            (((self.data[4] & 0b11111111) >> 0) <<  2) | \
            (((self.data[5] & 0b11000000) >> 6) <<  0)
        # fmt: on

    @property
    def marker_bit_1(self) -> int:
        return (self.data[5] & 0b00100000) >> 5

    @property
    def copyright_number_2(self) -> int:
        # fmt: off
        return \
            (((self.data[5] & 0b00011111) >> 0) << 17) | \
            (((self.data[6] & 0b11111111) >> 0) << 15) | \
            (((self.data[7] & 0b11111111) >> 0) <<  7) | \
            (((self.data[8] & 0b10000000) >> 7) <<  0)
        # fmt: on

    @property
    def marker_bit_2(self) -> int:
        return (self.data[8] & 0b01000000) >> 6

    @property
    def copyright_number_3(self) -> int:
        # fmt: off
        return \
            (((self.data[8]  & 0b00111111) >> 0) << 16) | \
            (((self.data[9]  & 0b11111111) >> 0) <<  8) | \
            (((self.data[10] & 0b11111111) >> 0) <<  0)
        # fmt: on


class FrameCenterOffset:
    def __init__(self, data: bytearray, i: int):
        self.data = data
        self.i = i

    @property
    def frame_centre_horizontal_offset(self) -> int:
        if self.i == 0:
            # fmt: off
            return \
                (((self.data[0] & 0b00001111) >> 0) << 12) | \
                (((self.data[1] & 0b11111111) >> 0) <<  4) | \
                (((self.data[2] & 0b11110000) >> 4) <<  0)
            # fmt: on
        elif self.i == 1:
            # fmt: off
            return \
                (((self.data[4] & 0b00000011) >> 0) << 14) | \
                (((self.data[5] & 0b11111111) >> 0) <<  6) | \
                (((self.data[6] & 0b11111100) >> 2) <<  0)
            # fmt: on
        else:
            # fmt: off
            return \
                (self.data[9])  << 8 | \
                (self.data[10]) << 0
            # fmt: on

    @property
    def marker_bit_0(self) -> int:
        if self.i == 0:
            return (self.data[2] & 0b00001000) >> 3
        elif self.i == 1:
            return (self.data[6] & 0b00000010) >> 1
        else:
            return (self.data[11] & 0b10000000) >> 7

    @property
    def frame_centre_vertical_offset(self) -> int:
        if self.i == 0:
            # fmt: off
            return \
                (((self.data[2] & 0b00000111) >> 0) << 13) | \
                (((self.data[3] & 0b11111111) >> 0) <<  5) | \
                (((self.data[4] & 0b11111000) >> 3) <<  0)
            # fmt: on
        elif self.i == 1:
            # fmt: off
            return \
                (((self.data[6] & 0b00000001) >> 0) << 15) | \
                (((self.data[7] & 0b11111111) >> 0) <<  7) | \
                (((self.data[8] & 0b11111110) >> 1) <<  0)
            # fmt: on
        else:
            # fmt: off
            return \
                (((self.data[11] & 0b01111111) >> 0) << 9) | \
                (((self.data[12] & 0b11111111) >> 0) <<  1) | \
                (((self.data[13] & 0b10000000) >> 7) <<  0)
            # fmt: on

    @property
    def marker_bit_1(self) -> int:
        if self.i == 0:
            return (self.data[4] & 0b00000100) >> 2
        elif self.i == 1:
            return (self.data[8] & 0b00000001) >> 0
        else:
            return (self.data[13] & 0b01000000) >> 6


class PictureDisplayExtension:
    def __init__(self, ed: ExtensionData, fh: BufferedReader):
        self.ed = ed
        self.frame_center_offsets: list[FrameCenterOffset] = []

        size = 4
        if self.ed.seq.number_of_frame_centre_offsets == 1:
            size = 5
        elif self.ed.seq.number_of_frame_centre_offsets == 2:
            size = 9
        elif self.ed.seq.number_of_frame_centre_offsets == 3:
            size = 14

        self.data: bytearray = bytearray(size)
        fh.readinto(self.data)

        for i in range(self.ed.seq.number_of_frame_centre_offsets):
            self.frame_center_offsets.append(FrameCenterOffset(self.data, i))

        next_start_code(fh)

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[0] & 0b11110000) >> 4


class PictureSpatialScalableExtension:
    def __init__(self, ed: ExtensionData, fh: BufferedReader):
        self.ed = ed

        self.data: bytearray = bytearray(7)
        fh.readinto(self.data)

        next_start_code(fh)

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def lower_layer_temporal_reference(self) -> int:
        # fmt: off
        return \
            (((self.data[0] & 0b00001111) >> 0) << 6) | \
            (((self.data[1] & 0b11111100) >> 2) << 0)
        # fmt: on

    @property
    def marker_bit_0(self) -> int:
        return (self.data[1] & 0b00000010) >> 1

    @property
    def lower_layer_horizontal_offset(self) -> int:
        # fmt: off
        return \
            (((self.data[1] & 0b00000001) >> 0) << 14) | \
            (((self.data[2] & 0b11111111) >> 0) <<  6) | \
            (((self.data[3] & 0b11111100) >> 2) <<  0)
        # fmt: on

    @property
    def marker_bit_1(self) -> int:
        return (self.data[3] & 0b00000010) >> 1

    @property
    def lower_layer_vertical_offset(self) -> int:
        # fmt: off
        return \
            (((self.data[3] & 0b00000001) >> 0) << 14) | \
            (((self.data[4] & 0b11111111) >> 0) <<  6) | \
            (((self.data[5] & 0b11111100) >> 4) <<  0)
        # fmt: on

    @property
    def spatial_temporal_weight_code_table_index(self) -> int:
        return (self.data[5] & 0b00000011) >> 2

    @property
    def lower_layer_progressive_frame(self) -> int:
        return (self.data[6] & 0b10000000) >> 7

    @property
    def lower_layer_deinterlaced_field_select(self) -> int:
        return (self.data[6] & 0b01000000) >> 6


class PictureTemporalScalableExtension:
    def __init__(self, ed: ExtensionData, fh: BufferedReader):
        self.ed = ed

        self.data: bytearray = bytearray(4)
        fh.readinto(self.data)

        next_start_code(fh)

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[0] & 0b11110000) >> 4

    @property
    def reference_select_code(self) -> int:
        return (self.data[0] & 0b00001100) >> 2

    @property
    def forward_temporal_reference(self) -> int:
        # fmt: off
        return \
            (((self.data[0] & 0b00000011) >> 0) << 8) | \
            (((self.data[1] & 0b11111111) >> 0) << 0)
        # fmt: on

    @property
    def marker_bit_0(self) -> int:
        return (self.data[2] & 0b10000000) >> 7

    @property
    def backward_temporal_reference(self) -> int:
        # fmt: off
        return \
            (((self.data[2] & 0b01111111) >> 0) << 5) | \
            (((self.data[3] & 0b11100000) >> 5) << 0)
        # fmt: on


class ExtensionData:
    def __init__(self, seq: Sequence, fh: BufferedReader, i: int):
        self.seq = seq

        self.data: bytearray = bytearray(4)
        fh.readinto(self.data)

        self.sequence_display_extension: SequenceDisplayExtension | None = None
        self.sequence_scalable_extension: SequenceScalableExtension | None = None
        self.quant_matrix_extension: QuantMatrixExtension | None = None
        self.copyright_extension: CopyrightExtension | None = None
        self.picture_display_extension: PictureDisplayExtension | None = None
        self.picture_spatial_scalable_extension: PictureSpatialScalableExtension | None = None
        self.picture_temporal_scalable_extension: PictureTemporalScalableExtension | None = None

        assert self.extension_start_code == extension_start_code
        assert i in (0, 2)

        next_bits = peek(fh, 1)[0]

        if i == 0:
            if next_bits == _c("Sequence Display Extension ID"):
                self.sequence_display_extension = SequenceDisplayExtension(self, fh)
            else:
                self.sequence_scalable_extension = SequenceScalableExtension(self, fh)

        if i == 2:
            if next_bits == _c("Quant Matrix Extension ID"):
                self.quant_matrix_extension = QuantMatrixExtension(self, fh)
            elif next_bits == _c("Copyright Extension ID"):
                self.copyright_extension = CopyrightExtension(self, fh)
            elif next_bits == _c("Picture Display Extension ID"):
                self.picture_display_extension = PictureDisplayExtension(self, fh)
            elif next_bits == _c("Picture Spatial Scalable Extension ID"):
                self.picture_spatial_scalable_extension = PictureSpatialScalableExtension(self, fh)
            else:
                self.picture_temporal_scalable_extension = PictureTemporalScalableExtension(self, fh)

    @property
    def extension_start_code(self) -> bytes:
        return self.data[:4]


class UserData:
    def __init__(self, seq: Sequence, fh: BufferedReader):
        self.seq = seq
        self.user_data: bytearray = bytearray()

        self.data: bytearray = bytearray(4)
        fh.readinto(self.data)

        more_data = True

        while more_data:
            next_bits = peek(fh, 3)
            more_data = next_bits != start_code_prefix
            if more_data:
                self.user_data = bytearray_extend(self.user_data, 1)
                self.user_data[-1:] = fh.read(1)

        next_start_code(fh)

    @property
    def user_data_start_code(self) -> bytes:
        return self.data[:4]


class GroupOfPictureHeader:
    def __init__(self, seq: Sequence, fh: BufferedReader):
        self.seq = seq
        self.user_data: bytearray = bytearray()

        self.data: bytearray = bytearray(8)
        fh.readinto(self.data)

        next_start_code(fh)

    @property
    def group_start_code(self) -> bytes:
        return self.data[:4]

    @property
    def time_code(self) -> int:
        # fmt: off
        return \
            (((self.data[4] & 0b11111111) >> 0) << 17) | \
            (((self.data[5] & 0b11111111) >> 0) <<  9) | \
            (((self.data[6] & 0b11111111) >> 0) <<  1) | \
            (((self.data[7] & 0b10000000) >> 7) <<  0)
        # fmt: on

    @property
    def closed_gop(self) -> int:
        return (self.data[7] & 0b01000000) >> 6

    @property
    def broken_link(self) -> int:
        return (self.data[7] & 0b00100000) >> 5


class PictureForward:
    def __init__(self, full_pel_forward_vector: int, forward_f_code: int):
        self.full_pel_forward_vector: int = full_pel_forward_vector
        self.forward_f_code = forward_f_code


class PictureBackward:
    def __init__(self, full_pel_backward_vector: int, backward_f_code: int):
        self.full_pel_backward_vector: int = full_pel_backward_vector
        self.backward_f_code: int = backward_f_code


class PictureExtra:
    def __init__(self, extra_bit_picture: int, extra_information_picture: int):
        self.extra_bit_picture: int = extra_bit_picture
        self.extra_information_picture: int = extra_information_picture


class PictureHeader:
    def __init__(self, seq: Sequence, fh: BufferedReader):
        self.seq = seq
        self.user_data: bytearray = bytearray()

        self.forward: PictureForward | None = None
        self.backward: PictureBackward | None = None
        self.extra: list[PictureExtra] = []

        self.data: bytearray = bytearray(8)
        fh.readinto(self.data)

        # a PictureHeader shall start with a `picture_start_code`
        assert self.picture_start_code == picture_start_code

        # TODO: improve BitStreamReader to handle starting point > 0
        fh.seek(-1, os.SEEK_CUR)
        br = BitStreamReader(fh, keep_data=True)
        br.read(5)

        if self.picture_coding_type == PictureCodingType.P or self.picture_coding_type == PictureCodingType.B:
            full_pel_forward_vector: int = br.read(1)
            forward_f_code: int = br.read(3)
            self.forward = PictureForward(full_pel_forward_vector, forward_f_code)

        if self.picture_coding_type == PictureCodingType.B:
            full_pel_backward_vector: int = br.read(1)
            backward_f_code: int = br.read(3)
            self.backward = PictureBackward(full_pel_backward_vector, backward_f_code)

        extra_bit_picture = br.read(1)

        while extra_bit_picture:
            extra_information_picture = br.read(8)
            picture_extra = PictureExtra(extra_bit_picture, extra_information_picture)
            self.extra.append(picture_extra)

        data = br.get_data()
        if data and len(data) > 1:
            self.data = bytearray_append(self.data, data[1:])

        next_start_code(fh)

    @property
    def picture_start_code(self) -> bytes:
        return self.data[:4]

    @property
    def temporal_reference(self) -> int:
        # fmt: off
        return \
            (((self.data[4] & 0b11111111) >> 0) << 2) | \
            (((self.data[5] & 0b11000000) >> 6) <<  0)
        # fmt: on

    @property
    def picture_coding_type(self) -> int:
        return (self.data[5] & 0b00111000) >> 3

    @property
    def vbv_delay(self) -> int:
        # fmt: off
        return \
            (((self.data[5] & 0b00000111) >> 0) << 13) | \
            (((self.data[6] & 0b11111111) >> 0) <<  5) | \
            (((self.data[7] & 0b11111000) >> 3) <<  0)
        # fmt: on

    def __repr__(self) -> str:
        picture_type = PictureCodingType(self.picture_coding_type)
        return f"PictureHeader(type={picture_type.name})"


class CompositeDisplayData:
    def __init__(self, pce: PictureCodingExtension, fh: BufferedReader):
        self.pce = pce

        self.data: bytearray = bytearray(3)
        fh.readinto(self.data)

    @property
    def v_axis(self) -> int:
        return (self.data[0] & 0b00100000) >> 5

    @property
    def field_sequence(self) -> int:
        return (self.data[0] & 0b00011100) >> 2

    @property
    def sub_carrier(self) -> int:
        return (self.data[0] & 0b00000010) >> 1

    @property
    def burst_amplitude(self) -> int:
        # fmt: off
        return \
            (((self.data[0] & 0b00000001) >> 0) << 6) | \
            (((self.data[1] & 0b11111100) >> 2) << 0)
        # fmt: on

    @property
    def sub_carrier_phase(self) -> int:
        # fmt: off
        return \
            (((self.data[1] & 0b00000011) >> 0) << 6) | \
            (((self.data[2] & 0b11111100) >> 2) << 0)
        # fmt: on

    def __str__(self) -> str:
        return (
            f"v_axis=0b{self.v_axis:b}\n"
            f"field_sequence=0b{self.field_sequence:b}\n"
            f"sub_carrier=0b{self.sub_carrier:b}\n"
            f"burst_amplitude=0x{self.burst_amplitude:X}\n"
            f"sub_carrier_phase=0x{self.sub_carrier_phase:X}\n"
        )


class PictureCodingExtension:
    def __init__(self, seq: Sequence, fh: BufferedReader):
        self.seq = seq
        self.user_data: bytearray = bytearray()
        self.composite_display_data: CompositeDisplayData | None = None

        self.data: bytearray = bytearray(9)
        fh.readinto(self.data)

        if self.composite_display_flag:
            fh.seek(-1, os.SEEK_CUR)
            self.composite_display_data = CompositeDisplayData(self, fh)

        assert self.extension_start_code == extension_start_code

        next_start_code(fh)

    @property
    def extension_start_code(self) -> bytes:
        return self.data[:4]

    @property
    def extension_start_code_identifier(self) -> int:
        return (self.data[4] & 0b11110000) >> 4

    @property
    def _forward_horizontal(self) -> int:
        return (self.data[4] & 0b00001111) >> 0

    @property
    def _forward_vertical(self) -> int:
        return (self.data[5] & 0b11110000) >> 4

    @property
    def _backward_horizontal(self) -> int:
        return (self.data[5] & 0b00001111) >> 0

    @property
    def _backward_vertical(self) -> int:
        return (self.data[6] & 0b11110000) >> 4

    @property
    def f_code(self) -> list[list[int]]:
        return [
            [
                self._forward_horizontal,
                self._forward_vertical,
            ],
            [
                self._backward_horizontal,
                self._backward_vertical,
            ],
        ]

    @property
    def intra_dc_precision(self) -> int:
        return (self.data[6] & 0b00001100) >> 2

    @property
    def picture_structure(self) -> int:
        return (self.data[6] & 0b00000011) >> 0

    @property
    def top_field_first(self) -> int:
        return (self.data[7] & 0b10000000) >> 7

    @property
    def frame_pred_frame_dct(self) -> int:
        return (self.data[7] & 0b01000000) >> 6

    @property
    def concealment_motion_vectors(self) -> int:
        return (self.data[7] & 0b00100000) >> 5

    @property
    def q_scale_type(self) -> int:
        return (self.data[7] & 0b00010000) >> 4

    @property
    def intra_vlc_format(self) -> int:
        return (self.data[7] & 0b00001000) >> 3

    @property
    def alternate_scan(self) -> int:
        return (self.data[7] & 0b00000100) >> 2

    @property
    def repeat_first_field(self) -> int:
        return (self.data[7] & 0b00000010) >> 1

    @property
    def chroma_420_type(self) -> int:
        return (self.data[7] & 0b00000001) >> 0

    @property
    def progressive_frame(self) -> int:
        return (self.data[8] & 0b10000000) >> 7

    @property
    def composite_display_flag(self) -> int:
        return (self.data[8] & 0b01000000) >> 6

    def __str__(self) -> str:
        str_ = (
            f"extension_start_code=0x{self.extension_start_code.hex().upper()}\n"
            f"extension_start_code_identifier=0b{self.extension_start_code_identifier:04b}\n"
            f"f_code[0][0]=0b{self.f_code[0][0]:04b}\n"
            f"f_code[0][1]=0b{self.f_code[0][1]:04b}\n"
            f"f_code[1][0]=0b{self.f_code[1][0]:04b}\n"
            f"f_code[1][1]=0b{self.f_code[1][1]:04b}\n"
            f"intra_dc_precision=0b{self.intra_dc_precision:02b}\n"
            f"picture_structure=0b{self.picture_structure:02b}\n"
            f"top_field_first={self.top_field_first}\n"
            f"frame_pred_frame_dct={self.frame_pred_frame_dct}\n"
            f"concealment_motion_vectors={self.concealment_motion_vectors}\n"
            f"q_scale_type={self.q_scale_type}\n"
            f"intra_vlc_format={self.intra_vlc_format}\n"
            f"alternate_scan={self.alternate_scan}\n"
            f"repeat_first_field={self.repeat_first_field}\n"
            f"chroma_420_type={self.chroma_420_type}\n"
            f"progressive_frame={self.progressive_frame}\n"
            f"composite_display_flag={self.composite_display_flag}\n"
        )
        if self.composite_display_flag:
            str_ += str(self.composite_display_data)
        return str_


class ExtraBitData:
    def __init__(self, extra_bit_slice: int, extra_information_slice: int):
        self.extra_bit_slice: int = extra_bit_slice
        self.extra_information_slice: int = extra_information_slice


class Slice:
    def __init__(self, seq: Sequence, fh: BufferedReader):
        self.seq: Sequence = seq

        self.slice_vertical_position_extension: int | None = None
        self.priority_breakpoint: int | None = None
        self.intra_slice_flag: int | None = None
        self.intra_slice: int | None = None
        self.reserved_bits: int | None = None
        self.extra_bit_data: list[ExtraBitData] = []
        self.macroblock_escape: int | None = None

        bs = BitStreamReader(fh, keep_data=True)

        bs.read(32)

        if self.seq.vertical_size > 2800:
            self.slice_vertical_position_extension = bs.read(3)

        if (
            self.seq.sequence_scalable_extension
            and self.seq.sequence_scalable_extension.scalable_mode == ScalableMode.data_partitioning
        ):
            self.priority_breakpoint = bs.read(7)

        self.quantiser_scale_code = bs.read(5)

        next_bit = bs.read(1)

        if next_bit == 1:
            self.intra_slice_flag = bs.read(1)
            self.intra_slice = bs.read(1)
            self.reserved_bits = bs.read(7)

            while next_bit := bs.read(1) == 1:
                extra_bit_slice = bs.read(1)
                extra_information_slice = bs.read(8)
                extra_bit_data = ExtraBitData(extra_bit_slice, extra_information_slice)
                self.extra_bit_data.append(extra_bit_data)

        assert next_bit == 0

        self.extra_bit_slice = next_bit

        data = bs.get_data()
        assert data is not None
        self.data: bytearray = bytearray(data)

        # next_bits = bs.read(11)

        # while next_bits == 0b00000001000:
        #     self.macroblock_escape = next_bits

        next_start_code(fh, check_zeros=False)

    @property
    def slice_start_code(self) -> bytes:
        return self.data[:4]


class Sequence:
    def __init__(self, m2v: MPEG2Video, fh: BufferedReader):
        self.m2v = m2v
        self.extension_data_list: list[ExtensionData] = []
        self.user_data_list: list[UserData] = []
        self.gop_header: GroupOfPictureHeader | None = None
        self.picture_coding_extension: PictureCodingExtension | None = None
        self.picture_header_list: list[PictureHeader] = []

        self.number_of_frame_centre_offsets: int = 0
        self.progressive_sequence: int = 0

        self.slice_list: list[Slice] = []

        self.sequence_header = SequenceHeader(self, fh)

        next_start_code(fh)

        next_bits = peek(fh, 4)

        if next_bits != extension_start_code:
            raise MPEG2FileFormatException("ISO/IEC 11172-2 (MPEG-1 Video) not supported")

        self.sequence_extension = SequenceExtension(self, fh)
        self.extension_and_user_data(fh, 0)

        next_bits = peek(fh, 4)

        # while next_bits != sequence_end_code and next_bits != sequence_header_code:
        while next_bits == picture_start_code or next_bits == group_start_code:
            if next_bits == group_start_code:
                self.group_of_pictures_header(fh)
                self.extension_and_user_data(fh, 1)

            picture_header = PictureHeader(self, fh)
            self.picture_header_list.append(picture_header)
            self.picture_coding_extension = PictureCodingExtension(self, fh)
            self.extension_and_user_data(fh, 2)

            # self.picture_data(fh)

            while data := fh.read(4096):
                try:
                    idx = data.index(sequence_header_code)
                except ValueError:
                    try:
                        idx = data.index(group_start_code)
                    except ValueError:
                        try:
                            idx = data.index(picture_start_code)
                        except ValueError:
                            try:
                                idx = data.index(sequence_end_code)
                            except ValueError:
                                idx = -1

                if idx >= 0:
                    fh.seek(idx - len(data), os.SEEK_CUR)
                    break

                fh.seek(-3, os.SEEK_CUR)

            next_bits = peek(fh, 4)
            pass

            # is_slice = True
            # while is_slice:
            #     next_start_code(fh, check_zeros=False)
            #     next_bits = peek(fh, 4)
            #     is_slice = is_slice_start_code(next_bits)
            #     if is_slice:
            #         fh.read(4)
            #     pass
            # print(next_bits.hex())

            # two GOP headers in the same GOP ???
            # assert next_bits != group_start_code

            # after a GOP should come other picture headers only ???
            # assert next_bits == picture_start_code or next_bits == sequence_header_code

    @property
    def vertical_size(self):
        return self.sequence_extension.vertical_size_extension << 12 | self.sequence_header.vertical_size_value

    @property
    def horizontal_size(self):
        return self.sequence_extension.horizontal_size_extension << 12 | self.sequence_header.horizontal_size_value

    @property
    def sequence_scalable_extension(self) -> SequenceScalableExtension | None:
        for extension_data in self.extension_data_list:
            if extension_data.sequence_scalable_extension:
                return extension_data.sequence_scalable_extension
        return None

    def group_of_pictures_header(self, fh: BufferedReader):
        self.gop_header = GroupOfPictureHeader(self, fh)

    def extension_and_user_data(self, fh: BufferedReader, i: int):
        found = True
        while found:
            next_bits = peek(fh, 4)
            found = next_bits == extension_start_code or next_bits == user_data_start_code
            if i != 1 and next_bits == extension_start_code:
                extension_data = ExtensionData(self, fh, i)
                self.extension_data_list.append(extension_data)
            if next_bits == user_data_start_code:
                user_data = UserData(self, fh)
                self.user_data_list.append(user_data)

    def picture_data(self, fh: BufferedReader):
        next_bits = peek(fh, 4)
        while is_slice_start_code(next_bits):
            slice = Slice(self, fh)
            self.slice_list.append(slice)
            next_bits = peek(fh, 4)  # ???
        next_start_code(fh, check_zeros=False)

    def __str__(self) -> str:
        width = self.sequence_header.horizontal_size_value
        height = self.sequence_header.vertical_size_value
        fps_code = self.sequence_header.frame_rate_code
        ar_info = self.sequence_header.aspect_ratio_information
        chroma_fmt = self.sequence_extension.chroma_format
        str_ = (
            f"MPEG-2 Video {width}x{height} {chroma_format_map[chroma_fmt]} "
            f"{frame_rate_map[fps_code]}fps {aspect_ratio_information_map[ar_info]}"
        )
        if self.picture_coding_extension:
            progressive = self.picture_coding_extension.progressive_frame
            if progressive:
                str_ += " progressive"
            else:
                str_ += " interlaced"
                if self.picture_coding_extension.top_field_first:
                    str_ += " (top field first)"
                else:
                    str_ += " (bottom field first)"
        return str_


class MPEG2Video:
    def __init__(self, fh: BufferedReader, identify_only: bool = False, info_only: bool = False):
        self.sequence_list: list[Sequence] = []

        # save current stream pos for later (we want to give back the reader
        # at the same position we received it)
        pos = fh.tell()

        try:
            next_bits = peek(fh, 4)

            assert next_bits == sequence_header_code

            while next_bits == sequence_header_code:
                sequence = Sequence(self, fh)
                self.sequence_list.append(sequence)
                next_bits = peek(fh, 4)

                if info_only:
                    return

            assert next_bits == sequence_end_code

        finally:
            # in any case, before leaving, reset the reader position
            fh.seek(pos)

    def __repr__(self) -> str:
        return str(self.sequence_list[0])
