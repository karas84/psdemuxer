from __future__ import annotations

from io import BufferedReader
from psdemuxer import MPEG2ProgramStream
from psdemuxer.io import SegmentInfo, BufferedStreamReader


class StreamIdReader(BufferedStreamReader):
    def __init__(self, m2ps: MPEG2ProgramStream, stream_id: str | int, fh: BufferedReader):
        self.pes_packets = list(m2ps.stream_iter(stream_id))
        self.segment_info: list[SegmentInfo] = []
        self.fh = fh

        data_so_far: int = 0
        for pes in self.pes_packets:
            segment = SegmentInfo(
                fh=fh,
                real_address=pes.pos + pes.header_length,
                virtual_start=data_so_far,
                data_size=pes.pes_packet_data_bytes_n,
            )
            data_so_far += pes.pes_packet_data_bytes_n
            self.segment_info.append(segment)

        super().__init__(self.segment_info)
