from __future__ import annotations

from functools import lru_cache


start_code_prefix = packet_start_code_prefix = b"\x00\x00\x01"
system_header_start_code = b"\x00\x00\x01\xbb"
program_end_code = b"\x00\x00\x01\xb9"


stream_ids = {
    0xBC: "program_stream_map",
    0xBD: "private_stream_1",
    0xBE: "padding_stream",
    0xBF: "private_stream_2",
    0xF0: "ECM_stream",
    0xF1: "EMM_stream",
    0xF2: "Rec. ITU-T H.222.0 | ISO/IEC 13818-1 Annex A or ISO/IEC 13818-6_DSMCC_stream",
    0xF3: "ISO/IEC_13522_stream",
    0xF4: "ISO/Rec. ITU-T H.222.1 type A",
    0xF5: "ISO/Rec. ITU-T H.222.1 type B",
    0xF6: "ISO/Rec. ITU-T H.222.1 type C",
    0xF7: "ISO/Rec. ITU-T H.222.1 type D",
    0xF8: "ISO/Rec. ITU-T H.222.1 type E",
    0xF9: "ancillary_stream",
    0xFA: "ISO/IEC 14496-1_SL-packetized_stream",
    0xFB: "ISO/IEC 14496-1_FlexMux_stream",
    0xFC: "metadata stream",
    0xFD: "extended_stream_id",
    0xFE: "reserved data stream",
    0xFF: "program_stream_directory",
}


def get_audio_stream_number(stream_id: int):
    if 0xC0 <= stream_id <= 0xDF:
        num = stream_id & 0b00011111
        return num

    return -1


def get_video_stream_number(stream_id: int):
    if 0xE0 <= stream_id <= 0xEF:
        num = stream_id & 0b00001111
        return num

    return -1


@lru_cache(maxsize=256)
def get_stream_name_by_id(stream_id: int) -> str | None:
    if (num := get_audio_stream_number(stream_id)) >= 0:
        return f"audio stream number {num}"

    if (num := get_video_stream_number(stream_id)) >= 0:
        return f"video stream number {num}"

    return stream_ids.get(stream_id, None)


@lru_cache(maxsize=256)
def get_stream_id_by_name(name: str) -> int | None:
    for num in range(0xBC, 0xFF + 1):
        stream_name = get_stream_name_by_id(num)
        if name == stream_name:
            return num

    return None
