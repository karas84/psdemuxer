from __future__ import annotations

import numpy as np

from io import BufferedReader, BytesIO
from enum import Enum
from ctypes import LittleEndianStructure, c_uint32, c_uint16, c_char, sizeof
from typing import Any, Generator
from psdemuxer.io import SegmentInfo, StreamReader

from psdemuxer.streams import WrongPrivateStream
from psdemuxer.pack.pes import PESPacket


class AudioType(int, Enum):
    PCM16BE = 0  # "PCM 16bit big endian"
    PCM16LE = 1  # "PCM 16bit little endian"
    VAG = 2  # "SPU2-ADPCM (VAG)"

    def to_string(self):
        if self == AudioType.PCM16BE:
            return "PCM 16bit big endian"
        elif self == AudioType.PCM16LE:
            return "PCM 16bit little endian"
        else:
            return "SPU2-ADPCM (VAG)"


class WAVHeader(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("chunk_id", c_char * 4),
        ("chunk_size", c_uint32),
        ("format", c_char * 4),
        ("fmt_chunk_id", c_char * 4),
        ("ftm_chunk_size", c_uint32),
        ("audio_format", c_uint16),
        ("num_channels", c_uint16),
        ("sample_rate", c_uint32),
        ("byte_rate", c_uint32),
        ("block_align", c_uint16),
        ("bits_per_sample", c_uint16),
        ("data_chunk_id", c_char * 4),
        ("data_chunk_size", c_uint32),
    ]

    def __init__(self):
        super().__init__()
        self.chunk_id: bytes = b"RIFF"
        self.chunk_size: int = 0
        self.format: bytes = b"WAVE"
        self.fmt_chunk_id: bytes = b"fmt "
        self.ftm_chunk_size: int = 0
        self.audio_format: int = 0
        self.num_channels: int = 0
        self.sample_rate: int = 0
        self.byte_rate: int = 0
        self.block_align: int = 0
        self.bits_per_sample: int = 0
        self.data_chunk_id: bytes = b"data"
        self.data_chunk_size: int = 0

    def __str__(self) -> str:
        str_ = ""
        for field_name, _ in self._fields_:  # type: ignore
            str_ += f"{field_name}: {getattr(self, field_name)}\n"
        return str_


def reinterleave(data: bytes):
    return np.frombuffer(data, dtype=np.uint16).reshape(2, -1).transpose(1, 0).reshape(-1).tobytes()


class _PS2PCMStream(StreamReader):
    def __init__(self, fh: BufferedReader, pes_iter: Generator[PESPacket, Any, None]):
        self.total_audio_data_size: int = 0
        self.audio_data_size: int = 0
        self.audio_interleave: int = 0
        self.num_channels: int = 1

        self._interleave_buffer_block: int = -1
        self._interleave_buffer_cache: bytes = b""

        segment_info: list[SegmentInfo] = []

        wav_header = WAVHeader()
        self.header_size = sizeof(wav_header)

        for n, pes in enumerate(pes_iter):
            is_first = n == 0
            ps2_audio = PS2PCMAudio(pes, fh, is_first)
            if is_first:
                self.total_audio_data_size = ps2_audio.total_audio_data_size
                self.audio_interleave = ps2_audio.interleave_size
                self.num_channels = ps2_audio.num_channels

                wav_header.chunk_size = 36 + self.total_audio_data_size
                wav_header.ftm_chunk_size = 16
                wav_header.audio_format = 1
                wav_header.num_channels = ps2_audio.num_channels
                wav_header.sample_rate = ps2_audio.sampling_rate
                wav_header.block_align = wav_header.num_channels * (16 // 8)
                wav_header.byte_rate = wav_header.sample_rate * wav_header.block_align
                wav_header.bits_per_sample = 16
                wav_header.data_chunk_size = self.total_audio_data_size

                # add header as first segment
                header_fh = BytesIO(wav_header)
                segment = SegmentInfo(
                    fh=header_fh,
                    real_address=0,
                    virtual_start=0,
                    data_size=self.header_size,
                )
                segment_info.append(segment)

            segment = SegmentInfo(
                fh=fh,
                real_address=pes.pos + ps2_audio.header_length,
                virtual_start=self.header_size + self.audio_data_size,
                data_size=ps2_audio.audio_data_size,
            )

            self.audio_data_size += ps2_audio.audio_data_size
            segment_info.append(segment)

        if not (self.audio_data_size == self.total_audio_data_size):
            # assume this is an encoder / muxer error and some final zero bytes were not written
            assert self.audio_data_size < self.total_audio_data_size
            missing_bytes = self.total_audio_data_size - self.audio_data_size
            # assume the missing bytes are less than an interleave block (only few bytes should be missing!)
            assert missing_bytes < self.audio_interleave
            print(
                f"WARNING: audio size mismatch (read != expected): "
                f"{self.audio_data_size} != {self.total_audio_data_size}. "
                f"Padding with {missing_bytes} extra bytes"
            )

            missing_fh = BytesIO(b"\x00" * missing_bytes)
            segment = SegmentInfo(
                fh=missing_fh,
                real_address=0,
                virtual_start=self.header_size + self.audio_data_size,
                data_size=missing_bytes,
            )

            self.audio_data_size += missing_bytes
            segment_info.append(segment)

        super().__init__(segment_info)

    def read(self, size: int = -1) -> bytes:
        if self.num_channels == 1:
            return super().read(size)

        pos = self.tell()

        remaining_bytes = self.header_size + self.total_audio_data_size - pos

        if not size >= 0:
            size = remaining_bytes
        else:
            size = min(size, remaining_bytes)

        interleave_size = self.audio_interleave * self.num_channels

        wants_header = pos < self.header_size

        if wants_header and (pos + size) < self.header_size:
            return super().read(size)

        to_read = size - self.header_size
        block_pos = max(0, pos - self.header_size)

        interleave_block_from = block_pos // interleave_size
        interleave_block_to = (block_pos + to_read) // interleave_size
        interleave_block_n = interleave_block_to - interleave_block_from + 1

        if wants_header:
            self.seek(0)
            interleaved_data = super().read(self.header_size)
            start = pos
        else:
            self.seek(self.header_size + interleave_block_from * interleave_size)
            interleaved_data = b""
            start = pos - self.header_size - interleave_block_from * interleave_size

        for interleave_block in range(interleave_block_from, interleave_block_from + interleave_block_n):
            if self._interleave_buffer_block != interleave_block:
                self.seek(self.header_size + interleave_block * interleave_size)
                data = super().read(interleave_size)
                self._interleave_buffer_block = interleave_block
                self._interleave_buffer_cache = reinterleave(data)

            interleaved_data += self._interleave_buffer_cache

        self.seek(pos + size)

        return interleaved_data[start : start + size]


class PS2PCMStream(BufferedReader):
    def __init__(self, fh: BufferedReader, pes_iter: Generator[PESPacket, Any, None]):
        self.stream_reader = _PS2PCMStream(fh, pes_iter)
        super().__init__(self.stream_reader, buffer_size=4096)


class PS2PCMAudio:
    full_header_length = 0x3F
    sub_header_length = 0x17
    block_data_start = 0x06

    def __init__(self, pes: PESPacket, fh: BufferedReader, is_first: bool = True):
        self.pes = pes
        self.is_first = is_first

        self._header_length = PS2PCMAudio.full_header_length if is_first else PS2PCMAudio.sub_header_length

        # save current stream pos for later (we want to give back the reader
        # at the same position we received it)
        pos = fh.tell()

        try:
            fh.seek(pes.pos)

            self.data: bytearray = bytearray(self._header_length)
            fh.readinto(self.data)

            if is_first and not (
                self.stream_id == b"\x00\x00\x01\xbd"
                and self.stream_audio_type in (0xA0, 0xA1)  # TODO: fix audio other than PCM
                and self.sshd == b"SShd"
                and self.audio_type in (0, 1, 2)  # TODO: fix audio other than PCM
                and self.interleave_size == 0x200  # TODO: fix audio other than PCM
                and self.ssbd == b"SSbd"
                and self.total_audio_data_size % (self.num_channels * 0x200) == 0  # TODO: fix audio other than PCM
            ):
                raise WrongPrivateStream()
            elif not is_first and not (
                self.stream_id == b"\x00\x00\x01\xbd"
                and self.stream_audio_type in (0xA0, 0xA1)  # TODO: fix audio other than PCM
            ):
                raise WrongPrivateStream()
        finally:
            # in any case, before leaving, reset the reader position
            fh.seek(pos)

    @property
    def header_length(self):
        return PS2PCMAudio.full_header_length if self.is_first else PS2PCMAudio.sub_header_length

    @property
    def stream_id(self) -> bytes:
        return self.data[:4]

    @property
    def block_size(self) -> int:
        return self.data[4] << 8 | self.data[5]

    @property
    def block_size_data(self) -> bytearray:
        return self.data[0x06:0x14]

    @property
    def stream_audio_type(self) -> int:
        return self.data[0x14]

    @property
    def stream_number(self) -> int:
        return self.data[0x15] << 8 | self.data[0x16]

    @property
    def sshd(self) -> bytes:
        assert self.is_first
        return self.data[0x17:0x1B]

    @property
    def subheader_length(self) -> int:
        assert self.is_first
        return self.data[0x1B] << 24 | self.data[0x1C] << 16 | self.data[0x1D] << 8 | self.data[0x1E]

    @property
    def audio_type(self) -> int:
        assert self.is_first
        return self.data[0x1F] | self.data[0x20] << 8 | self.data[0x21] << 16 | self.data[0x22] << 24

    @property
    def sampling_rate(self) -> int:
        assert self.is_first
        return self.data[0x23] | self.data[0x24] << 8 | self.data[0x25] << 16 | self.data[0x26] << 24

    @property
    def num_channels(self) -> int:
        assert self.is_first
        return self.data[0x27] | self.data[0x28] << 8 | self.data[0x29] << 16 | self.data[0x2A] << 24

    @property
    def interleave_size(self) -> int:
        assert self.is_first
        return self.data[0x2B] | self.data[0x2C] << 8 | self.data[0x2D] << 16 | self.data[0x2E] << 24

    @property
    def loop_start_block_address(self) -> int:
        assert self.is_first
        return self.data[0x2F] | self.data[0x30] << 8 | self.data[0x31] << 16 | self.data[0x32] << 24

    @property
    def loop_end_block_address(self) -> int:
        assert self.is_first
        return self.data[0x33] | self.data[0x34] << 8 | self.data[0x35] << 16 | self.data[0x36] << 24

    @property
    def ssbd(self) -> bytes:
        assert self.is_first
        return self.data[0x37:0x3B]

    @property
    def total_audio_data_size(self) -> int:
        assert self.is_first
        return self.data[0x3B] | self.data[0x3C] << 8 | self.data[0x3D] << 16 | self.data[0x3E] << 24

    @property
    def audio_data_size(self) -> int:
        header_size = self._header_length - PS2PCMAudio.block_data_start
        return self.block_size - header_size

    def __str__(self):
        audio_type_str = AudioType(self.audio_type).to_string()
        return f"PS2 AUDIO ({audio_type_str}) {self.num_channels} channel(s) {self.sampling_rate} Hz"
