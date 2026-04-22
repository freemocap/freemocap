import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReleaseNoteContent:
    """Data class to hold content for a release note tab."""
    tab_title: str
    content_title: str
    content_html: str
    content_subtitle: str | None = None
    image_path: str | None = None
    logo_path: str | None = None
    tab_order: int = 0
    latest: bool = False


def get_all_release_notes() -> list[ReleaseNoteContent]:
    from freemocap.gui.qt.widgets.release_notes_dialogs.versions.v180_release_notes import get_v180_release_notes
    from freemocap.gui.qt.widgets.release_notes_dialogs.versions.v170_release_notes import get_v170_release_notes
    from freemocap.gui.qt.widgets.release_notes_dialogs.versions.v160_release_notes import get_v160_release_notes
    from freemocap.gui.qt.widgets.release_notes_dialogs.versions.v154_release_notes import get_v154_release_notes
    from freemocap.gui.qt.widgets.release_notes_dialogs.versions.older_versions_release_notes import get_older_versions_release_notes

    release_notes = [
        get_v180_release_notes(),
        get_v170_release_notes(),
        get_v160_release_notes(),
        get_v154_release_notes(),
        get_older_versions_release_notes(),
    ]

    return sorted(release_notes, key=lambda x: x.tab_order)
