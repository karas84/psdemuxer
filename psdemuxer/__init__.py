from __future__ import annotations

from io import BufferedReader
from typing import Generator, Any

from psdemuxer.pack import PackStartHeader
from psdemuxer.utils import peek
from psdemuxer.pack.pes import PESPacket
from psdemuxer.constants import program_end_code, get_stream_id_by_name


class MPEG2ProgramStream:
    def __init__(self, fh: BufferedReader):
        self.pack_list: list[PackStartHeader] = []
        self.pes_types: dict[int, PESPacket] = {}

        while True:
            psh = PackStartHeader(fh)
            self.pack_list.append(psh)

            for pes in psh.pes_list:
                if pes.stream_id not in self.pes_types:
                    self.pes_types[pes.stream_id] = pes

            next_bits = peek(fh, 4)

            if next_bits == program_end_code:
                break

    def streams(self) -> Generator[tuple[int, PESPacket], Any, None]:
        for stream_id, pes in self.pes_types.items():
            yield stream_id, pes

    def stream_iter(self, stream_id: int | str) -> Generator[PESPacket, Any, None]:
        if isinstance(stream_id, str):
            stream_id_ = get_stream_id_by_name(stream_id)
            if stream_id_ is None:
                raise ValueError(f"invalid stream_id ({stream_id})")
            stream_id = stream_id_

        if stream_id not in self.pes_types:
            raise ValueError(f"stream_id ({stream_id}) not found")

        for psh in self.pack_list:
            for pes in psh.pes_list:
                if pes.stream_id == stream_id:
                    yield pes

    def __len__(self) -> int:
        return sum(len(psh) for psh in self.pack_list)
