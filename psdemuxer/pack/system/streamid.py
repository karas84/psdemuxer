from __future__ import annotations

from io import BufferedReader

from psdemuxer.exceptions import InvalidFixedBitsException


class StreamId:
    size = 3

    def __init__(self, fh: BufferedReader):
        self.pos = fh.tell()
        self.data: bytearray = bytearray(StreamId.size)
        fh.readinto(self.data)

        if self.b_11 != 0b11:
            raise InvalidFixedBitsException()

    @property
    def stream_id(self) -> int:
        return (self.data[0] & 0b11111111) >> 0

    @property
    def b_11(self) -> int:
        return (self.data[1] & 0b11000000) >> 6

    @property
    def p_std_buffer_bound_scale(self) -> int:
        return (self.data[1] & 0b00100000) >> 5

    @property
    def p_std_buffer_size_bound(self) -> int:
        # fmt: off
        return \
            ((self.data[1] & 0b00011111) >> 0) << 8 | \
            ((self.data[2] & 0b11111111) >> 0) << 0
        # fmt: on

    def __str__(self) -> str:
        str_ = f"-- 0x{self.pos:X} SystemHeaderStreamId --\n"
        str_ += "\n".join(
            [
                f"stream_id=0x{self.stream_id:X}",
                f"b_11=0b{self.b_11:b}",
                f"p_std_buffer_bound_scale={self.p_std_buffer_bound_scale}",
                f"p_std_buffer_size_bound={self.p_std_buffer_size_bound}",
            ]
        )
        return str_

    def __repr__(self) -> str:
        return f"---- 0x{self.pos:08X} 0x{self.stream_id:02X}"


class StreamIdEx:
    stream_id_ex = 0b10110111
    size = 6

    def __init__(self, fh: BufferedReader):
        self.pos = fh.tell()
        self.data: bytearray = bytearray(StreamIdEx.size)
        fh.readinto(self.data)
        assert self.data[0] == StreamIdEx.stream_id

        if self.b_11_0 != 0b11 or self.b_0000000 != 0b0000000 or self.b_10110110 != 0b10110110 or self.b_11_1 != 0b11:
            raise InvalidFixedBitsException()

    @property
    def stream_id(self) -> int:
        return (self.data[0] & 0b11111111) >> 0

    @property
    def b_11_0(self) -> int:
        return (self.data[1] & 0b11000000) >> 6

    @property
    def b_0000000(self) -> int:
        # fmt: off
        return \
            ((self.data[1] & 0b00111111) >> 0) << 1 | \
            ((self.data[2] & 0b10000000) >> 7) << 0
        # fmt: on

    @property
    def stream_id_extension(self) -> int:
        return (self.data[2] & 0b011111111) >> 0

    @property
    def b_10110110(self) -> int:
        return (self.data[3] & 0b111111111) >> 0

    @property
    def b_11_1(self) -> int:
        return (self.data[4] & 0b11000000) >> 6

    @property
    def p_std_buffer_bound_scale(self) -> int:
        return (self.data[4] & 0b00100000) >> 5

    @property
    def p_std_buffer_size_bound(self) -> int:
        # fmt: off
        return \
            ((self.data[4] & 0b00011111) >> 0) << 8 | \
            ((self.data[5] & 0b11111111) >> 0) << 0
        # fmt: on

    def __str__(self) -> str:
        str_ = f"-- 0x{self.pos:X} SystemHeaderStreamIdEx --\n"
        str_ += "\n".join(
            [
                f"stream_id=0x{self.stream_id:X}",
                f"b_11_0=0x{self.b_11_0:X}",
                f"b_0000000=0x{self.b_0000000:X}",
                f"stream_id_extension=0x{self.stream_id_extension:X}",
                f"b_10110110=0x{self.b_10110110:X}",
                f"b_11_1=0x{self.b_11_1:X}",
                f"p_std_buffer_bound_scale={self.p_std_buffer_bound_scale}",
                f"p_std_buffer_size_bound={self.p_std_buffer_size_bound}",
            ]
        )
        return str_

    def __repr__(self) -> str:
        return f"---- 0x{self.pos:08X} 0x{self.stream_id:02X}"
