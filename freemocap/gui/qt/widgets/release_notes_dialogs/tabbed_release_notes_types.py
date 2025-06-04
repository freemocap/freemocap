from enum import Enum


class ReleaseNotesDisplayOption(Enum):
    """Enum for release notes display options."""

    SHOW_ON_STARTUP = "Show on startup"
    SHOW_ON_NEW_RELEASE = "Show only for new releases"
    NEVER_SHOW = "Never show"
