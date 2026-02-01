from __future__ import annotations


class MPEG2FileFormatException(Exception):
    pass


class InvalidFixedBitsException(MPEG2FileFormatException):
    pass


class InvalidMarkerException(MPEG2FileFormatException):
    pass
