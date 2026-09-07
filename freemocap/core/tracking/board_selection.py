"""Board layout selection shared by recording tasks."""

from enum import StrEnum


class CharucoBoardMode(StrEnum):
    AUTO = "auto"
    EXPLICIT = "explicit"
