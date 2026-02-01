from __future__ import annotations

import time
import argparse

from typing import Protocol, cast
from signal import signal, SIGPIPE, SIG_DFL
from pathlib import Path

from psdemuxer.constants import get_stream_name_by_id, get_stream_id_by_name, get_video_stream_number
from psdemuxer import MPEG2ProgramStream
from psdemuxer.streams import WrongPrivateStream
from psdemuxer.streams.private.dvdac3 import DVDAC3Audio, DVDAC3Stream
from psdemuxer.streams.private.ps2pcm import PS2PCMAudio, PS2PCMStream
from psdemuxer.streams.reader import StreamIdReader
from psdemuxer.streams.video.mpeg2video import MPEG2Video


signal(SIGPIPE, SIG_DFL)


private_stream_1 = get_stream_id_by_name("private_stream_1")


def main():
    class ArgsProtocol(Protocol):
        mpeg_ps_file: Path
        out_dir: Path | None

    parser = argparse.ArgumentParser(description="MPEG-PS File Demultiplexer")
    parser.add_argument(
        "mpeg_ps_file",
        metavar="mpeg-ps-file",
        type=Path,
        help="Input MPEG-PS file to demultiplex",
    )
    parser.add_argument(
        "--extract",
        dest="out_dir",
        type=Path,
        help="Output path to extract supported tracks to (it will be created if necessary)",
    )

    args = cast(ArgsProtocol, parser.parse_args())

    t = time.perf_counter()

    with args.mpeg_ps_file.open(mode="rb") as fh:
        mpeg2_program_stream = MPEG2ProgramStream(fh)

        print(f"Parsing '{args.mpeg_ps_file}'")
        print(f"Found {len(mpeg2_program_stream)} PES Packets")

        has_video_0 = False
        ps2_audio = None
        ac3_dvd_audio = None

        for n, (stream_id, pes) in enumerate(mpeg2_program_stream.streams()):
            stream_name = get_stream_name_by_id(stream_id)
            video_stream_num = get_video_stream_number(stream_id)

            if video_stream_num >= 0:
                has_video_0 = True
                video_stream_name = f"video_stream_{video_stream_num}"

                bsr = StreamIdReader(mpeg2_program_stream, "video stream number 0", fh)
                m2v = MPEG2Video(bsr, info_only=True)

                video_stream_str = f" ({m2v})"
                print(f"Stream {n}: {video_stream_name}{video_stream_str} (0x{stream_id:02X})")

            elif stream_name == "private_stream_1":
                private_stream_str = ""

                try:
                    ps2_audio = PS2PCMAudio(pes, fh, is_first=True)
                    private_stream_str = f" ({ps2_audio})"
                except WrongPrivateStream:
                    pass

                try:
                    ac3_dvd_audio = DVDAC3Audio(pes, fh, is_first=True)
                    private_stream_str = f" ({ac3_dvd_audio})"
                except WrongPrivateStream:
                    pass

                print(f"Stream {n}: {stream_name}{private_stream_str} (0x{stream_id:02X})")

            else:
                print(f"Stream {n}: {stream_name} (0x{stream_id:02X})")

        if args.out_dir:
            # extract known streams

            args.out_dir.mkdir(parents=True, exist_ok=True)

            if has_video_0:
                bsr = StreamIdReader(mpeg2_program_stream, "video stream number 0", fh)
                m2v = MPEG2Video(bsr)

                print(f"Extracting {m2v} ...")

                with (args.out_dir / f"{args.mpeg_ps_file.stem}_stream.m2v").open(mode="wb+") as wh:
                    extracted_data_size = 0
                    while data := bsr.read(4096):
                        wh.write(data)
                        extracted_data_size += len(data)

                print(f"Extracted {extracted_data_size} bytes of MPEG-2 Video")

            if ps2_audio:
                print("Extracting PS2 Audio ...")

                stream_iter = mpeg2_program_stream.stream_iter("private_stream_1")
                pcm_stream = PS2PCMStream(fh, stream_iter)

                with (args.out_dir / f"{args.mpeg_ps_file.stem}_stream.wav").open(mode="wb+") as wh:
                    extracted_data_size = 0
                    while data := pcm_stream.read(4096):
                        wh.write(data)
                        extracted_data_size += len(data)

                print(f"Extracted {extracted_data_size} bytes of PS2 PCM audio")

            if ac3_dvd_audio:
                print("Extracting DVD AC-3 Audio ...")

                stream_iter = mpeg2_program_stream.stream_iter("private_stream_1")
                ac3_stream = DVDAC3Stream(fh, stream_iter)

                with (args.out_dir / f"{args.mpeg_ps_file.stem}_stream.ac3").open(mode="wb+") as wh:
                    extracted_data_size = 0
                    while data := ac3_stream.read(4096):
                        wh.write(data)
                        extracted_data_size += len(data)

                print(f"Extracted {extracted_data_size} bytes of AC-3 audio")

        t = time.perf_counter() - t

        print(f"Done in {t:.3f} seconds")


if __name__ == "__main__":
    main()
