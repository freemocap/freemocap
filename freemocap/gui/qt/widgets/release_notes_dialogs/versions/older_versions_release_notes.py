from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_content import ReleaseNoteContent


def get_older_versions_release_notes() -> ReleaseNoteContent:
    return ReleaseNoteContent(
        tab_title="Older Versions",
        content_title="Previous Versions",
        content_html="""
        <p>For information about older versions, please visit our
        <a href='https://github.com/freemocap/freemocap/releases'>GitHub releases page</a>.</p>
        """,
        logo_path=None,
        tab_order=4,
    )
