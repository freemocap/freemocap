from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_content import ReleaseNoteContent
from freemocap.gui.qt.widgets.release_notes_dialogs.versions._image_paths import SKELLY_HEART_EYES_PNG

_HTML = """
<html>
<style>
    a { color: #ccc; text-decoration: none; font-weight: 500; }
    .emphasis { color: #aaa; font-weight: bold; }
</style>
<body>
<p>
    So, remember last time when we said we were going to add a
    <a href="https://github.com/freemocap/freemocap/pull/676">set of comprehensive quality assurance diagnostics</a>
    to ensure monotonically increasing data quality?
    <br/><br/>
    Well, we did that and immediately discovered a bug in our calibration/reconstruction pipeline that has apparently
    been causing a ~10–15% scaling offset to our data (i.e. measured limb segment lengths would be ~85–115% of their
    real-world lengths).
    <br/><br/>
    Good news is that we fixed it, so our data should be more accurately scaled to real-world units! We call that
    progress 😌
    <br/><br/>
    If your application requires empirical accuracy, we recommend reprocessing any critical data with the latest
    version of FreeMoCap to ensure the highest quality results.
    <br/><br/>
    See <a href="https://github.com/freemocap/freemocap/pull/681">Issue #681</a> for a full run-down on the code
    sleuthing and thread-pulling that led to this fix.
    <br/>--<br/>
    For additional details about what's new in v1.6.3 — see
    <a href="https://github.com/freemocap/freemocap/releases/tag/v1.6.3">the official release page</a>.
    <br/><br/>
    (You can always access these release notes from the <b>Help</b> menu.)
</p>
</body>
</html>
"""


def get_v160_release_notes() -> ReleaseNoteContent:
    return ReleaseNoteContent(
        latest=False,
        tab_title="v1.6.0 Data Scaling",
        content_title="FreeMoCap v1.6.0 - Data Scaling improvement!",
        content_html=_HTML,
        logo_path=SKELLY_HEART_EYES_PNG,
        tab_order=2,
    )
