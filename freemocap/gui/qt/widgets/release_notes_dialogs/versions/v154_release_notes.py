from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_content import ReleaseNoteContent
from freemocap.gui.qt.widgets.release_notes_dialogs.versions._image_paths import SKELLY_SWEAT_PNG

_HTML = """
<html>
<style>
    a { color: #ccc; text-decoration: none; font-weight: 500; }
    .emphasis { color: #aaa; font-weight: bold; }
</style>
<body>
<p style="font-size: 18px; font-weight: bold; color: #f5a; margin-bottom: 15px;">Whoops!!</p>
<p style="font-size: 16px; font-weight: semibold; color: #fc8; margin-bottom: 15px;">
    Possible data quality regression in versions 1.4.7–1.5.3
</p>
<p>
    We identified and fixed a bug in <b>v1.4.7–v1.5.3 (10 Oct 2024 – 10 Mar 2025)</b> that caused the pipeline to skip
    Butterworth filtering during processing
    (<a href="https://github.com/freemocap/freemocap/pull/675">Bugfix PR</a>).
    Recordings from these versions may have increased noise/jitter/shakiness in the final keypoint trajectories.
    <br/><br/>
    Based on your application, the difference may or may not be noticeable. It is most likely to affect users whose
    applications focus on fine-grained trajectories of the hands and limbs (especially for scientific analysis).
    <br/><br/>
    <b>We recommend reprocessing any critical data collected during this period with the latest version of FreeMoCap
    to ensure the highest quality results.</b>
    <br/><br/>
    You may also filter the data in Blender (see
    <a href="https://www.youtube.com/watch?v=33OhM5xFUlg">this tutorial by Flux Renders</a>).
    <br/>--<br/>
    In preparation for the release of FreeMoCap v2.0 (optimistically Summer 2025), we are implementing a
    <a href="https://github.com/freemocap/freemocap/pull/676">set of comprehensive quality assurance diagnostics</a>
    to ensure that the quality of our output is strictly monotonic across future versions.
</p>
<p style="font-size: 13px; margin-top: 20px; color: #7f8c8d;">
    Thanks to
    (<a href="https://discord.com/channels/760487252379041812/760489602917466133/1346487740568440983">@larap for reporting</a>),
    and to the rest of the FreeMoCap community for their help in developing this project.
</p>
</body>
</html>
"""


def get_v154_release_notes() -> ReleaseNoteContent:
    return ReleaseNoteContent(
        tab_title="v1.5.4 Butterworth Filter Fix",
        content_title="Butterworth Filter Fix in v1.5.4",
        content_html=_HTML,
        logo_path=SKELLY_SWEAT_PNG,
        tab_order=3,
    )
