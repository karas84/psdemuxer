from __future__ import annotations

from io import BufferedReader
from typing import Any, Generator

from psdemuxer.io import BufferedStreamReader, SegmentInfo
from psdemuxer.streams import WrongPrivateStream
from psdemuxer.pack.pes import PESPacket
from psdemuxer.constants import get_stream_id_by_name as _s
from psdemuxer.utils import peek


class DVDAC3Stream(BufferedStreamReader):
    def __init__(self, fh: BufferedReader, pes_iter: Generator[PESPacket, Any, None]):
        segment_info: list[SegmentInfo] = []

        data_so_far = 0
        for n, pes in enumerate(pes_iter):
            is_first = n == 0
            ac3_audio = DVDAC3Audio(pes, fh, is_first)

            segment = SegmentInfo(
                fh=fh,
                real_address=pes.pos + pes.header_length + DVDAC3Audio.ac3_header_length,
                virtual_start=data_so_far,
                data_size=ac3_audio.data_length,
            )
            data_so_far += ac3_audio.data_length
            segment_info.append(segment)

        super().__init__(segment_info)


class DVDAC3Audio:
    ac3_substream_number = 0x80
    ac3_header_length = 0x04
    ac3_sync_word = b"\x0B\x77"

    def __init__(self, pes: PESPacket, fh: BufferedReader, is_first: bool = True):
        self.pes = pes
        self.is_first = is_first

        # a DVD AC-3 stream must reside in a `private_stream_1` PES stream, which must have
        # a header size of 17 (0x11)
        if not (self.pes.stream_id == _s("private_stream_1") and self.pes.header_length == 0x11):
            raise WrongPrivateStream()

        # save current stream pos for later (we want to give back the reader
        # at the same position we received it)
        pos = fh.tell()

        try:
            fh.seek(pes.pos + pes.header_length)

            self.data: bytearray = bytearray(4)
            fh.readinto(self.data)

            sync_word = peek(fh, 2)

            if is_first and (
                not self.stream_id == DVDAC3Audio.ac3_substream_number or not sync_word == DVDAC3Audio.ac3_sync_word
            ):
                raise WrongPrivateStream()
        finally:
            # in any case, before leaving, reset the reader position
            fh.seek(pos)

    @property
    def data_length(self):
        return self.pes.pes_packet_data_bytes_n - DVDAC3Audio.ac3_header_length

    @property
    def stream_id(self) -> int:
        return self.data[0]

    @property
    def header_size(self) -> int:
        return DVDAC3Audio.ac3_header_length

    @property
    def audio_frame_n(self) -> int:
        return self.data[1]

    @property
    def pts_packet_offset(self) -> int:
        return self.data[2] << 8 | self.data[3]

    def __str__(self):
        return f"DVD AC-3 AUDIO"
