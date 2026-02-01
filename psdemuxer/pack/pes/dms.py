from __future__ import annotations

from enum import Enum
from io import BufferedReader

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psdemuxer.pack.pes.flagdata import FlagData


class TrickModeControl(int, Enum):
    fast_forward = 0b000
    slow_motion = 0b001
    freeze_frame = 0b010
    fast_reverse = 0b011
    slow_reverse = 0b100
    reserved_1 = 0b101
    reserved_2 = 0b110
    reserved_3 = 0b111


class DMSTrickModeFastForward:
    def __init__(self, pes_tmc: DMSTrickModeControl, data: bytearray):
        self.pes_tmc: DMSTrickModeControl = pes_tmc
        self.data: bytearray = data

    @property
    def field_id(self) -> int:
        return (self.data[0] & 0b00011000) >> 3

    @property
    def intra_slice_refresh(self) -> int:
        return (self.data[0] & 0b00000100) >> 2

    @property
    def frequency_truncation(self) -> int:
        return (self.data[0] & 0b00000011) >> 0

    def __str__(self) -> str:
        return (
            f"field_id=0b{self.field_id:b}\n"
            f"intra_slice_refresh=0b{self.intra_slice_refresh:b}\n"
            f"frequency_truncation=0b{self.frequency_truncation:b}\n"
        )


class DMSTrickModeSlowMotion:
    def __init__(self, pes_tmc: DMSTrickModeControl, data: bytearray):
        self.pes_tmc: DMSTrickModeControl = pes_tmc
        self.data: bytearray = data

    @property
    def rep_cntrl(self) -> int:
        return (self.data[0] & 0b00011111) >> 0

    def __str__(self) -> str:
        return f"rep_cntrl=0b{self.rep_cntrl:b}\n"


class DMSTrickModeFreezeFrame:
    def __init__(self, pes_tmc: DMSTrickModeControl, data: bytearray):
        self.pes_tmc: DMSTrickModeControl = pes_tmc
        self.data: bytearray = data

    @property
    def field_id(self) -> int:
        return (self.data[0] & 0b00011000) >> 3

    @property
    def reserved(self) -> int:
        return (self.data[0] & 0b00000111) >> 0

    def __str__(self) -> str:
        # fmt: off
        return (
            f"field_id=0b{self.field_id:b}\n"
            f"reserved=0b{self.reserved:b}\n"
        )
        # fmt: on


class DMSTrickModeFastReverse:
    def __init__(self, pes_tmc: DMSTrickModeControl, data: bytearray):
        self.pes_tmc: DMSTrickModeControl = pes_tmc
        self.data: bytearray = data

    @property
    def field_id(self) -> int:
        return (self.data[0] & 0b00011000) >> 3

    @property
    def intra_slice_refresh(self) -> int:
        return (self.data[0] & 0b00000100) >> 2

    @property
    def frequency_truncation(self) -> int:
        return (self.data[0] & 0b00000011) >> 0

    def __str__(self) -> str:
        return (
            f"field_id=0b{self.field_id:b}\n"
            f"intra_slice_refresh=0b{self.intra_slice_refresh:b}\n"
            f"frequency_truncation=0b{self.frequency_truncation:b}\n"
        )


class DMSTrickModeSlowReverse:
    def __init__(self, pes_tmc: DMSTrickModeControl, data: bytearray):
        self.pes_tmc: DMSTrickModeControl = pes_tmc
        self.data: bytearray = data

    @property
    def rep_cntrl(self) -> int:
        return (self.data[0] & 0b11111111) >> 0

    def __str__(self) -> str:
        return f"rep_cntrl=0b{self.rep_cntrl:b}\n"


class DMSTrickModeReserved:
    def __init__(self, pes_tmc: DMSTrickModeControl, data: bytearray):
        self.pes_tmc: DMSTrickModeControl = pes_tmc
        self.data: bytearray = data

    @property
    def reserved(self) -> int:
        return (self.data[0] & 0b11111111) >> 0

    def __str__(self) -> str:
        return f"reserved=0b{self.reserved:b}\n"


class DMSTrickModeControl:
    def __init__(self, pes_pfd: FlagData, fh: BufferedReader):
        self.pes_pfd: FlagData = pes_pfd
        self.data: bytearray = bytearray(1)

        fh.readinto(self.data)

        if self.trick_mode_control == TrickModeControl.fast_forward:
            self.tmc = DMSTrickModeFastForward(self, self.data)
        elif self.trick_mode_control == TrickModeControl.slow_motion:
            self.tmc = DMSTrickModeSlowMotion(self, self.data)
        elif self.trick_mode_control == TrickModeControl.freeze_frame:
            self.tmc = DMSTrickModeFreezeFrame(self, self.data)
        elif self.trick_mode_control == TrickModeControl.fast_reverse:
            self.tmc = DMSTrickModeFastReverse(self, self.data)
        elif self.trick_mode_control == TrickModeControl.slow_reverse:
            self.tmc = DMSTrickModeSlowReverse(self, self.data)
        else:  # reserved
            self.tmc = DMSTrickModeReserved(self, self.data)

    @property
    def trick_mode_control(self) -> int:
        return (self.data[0] & 0b11100000) >> 5

    def __str__(self) -> str:
        return f"{self.tmc}"
