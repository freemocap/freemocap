from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl

from freemocap.system.paths_and_filenames.file_and_folder_names import PATH_TO_FREEMOCAP_LOGO_SVG
import logging
logger = logging.getLogger(__name__)

SKELLY_LOGO_BASE_SVG_FILENAME = "freemocap-logo-black-border.svg"
SKELLY_SWEAT_PNG = PATH_TO_FREEMOCAP_LOGO_SVG.replace(
    SKELLY_LOGO_BASE_SVG_FILENAME, "skelly-sweat.png")
SKELLY_HEART_EYES_PNG = PATH_TO_FREEMOCAP_LOGO_SVG.replace(
    SKELLY_LOGO_BASE_SVG_FILENAME, "skelly-heart-eyes.png")
SKELLY_THIS_WAY_UP_PNG = PATH_TO_FREEMOCAP_LOGO_SVG.replace(
    SKELLY_LOGO_BASE_SVG_FILENAME, "skelly-this-way-up.png")

CHARUCO_AS_GROUND_PLANE_PNG = Path(PATH_TO_FREEMOCAP_LOGO_SVG).parent.parent / "charuco/charuco_as_groundplane.png"

if not Path(SKELLY_SWEAT_PNG).exists():
    logger.warning(f"Could not find {SKELLY_SWEAT_PNG}")
if not Path(SKELLY_HEART_EYES_PNG).exists():
    logger.warning(f"Could not find {SKELLY_HEART_EYES_PNG}")
if not Path(SKELLY_THIS_WAY_UP_PNG).exists():
    logger.warning(f"Could not find {SKELLY_THIS_WAY_UP_PNG}")
if not Path(CHARUCO_AS_GROUND_PLANE_PNG).exists():
    logger.warning(f"Could not find {CHARUCO_AS_GROUND_PLANE_PNG}")

@dataclass
class ReleaseNoteContent:
    """Data class to hold content for a release note tab."""

    tab_title: str
    content_title: str
    content_html: str
    content_subtitle: str | None = None
    image_path: str | None = None
    logo_path: str | None = None
    tab_order: int = 0  # Lower numbers appear first
    latest: bool = False



def get_v170_release_notes() -> ReleaseNoteContent:
    """Return the release notes for v1.7.0."""

    return ReleaseNoteContent(
        latest=True,
        logo_path=SKELLY_THIS_WAY_UP_PNG,  # Using the "this way up" logo since it's about orientation
        image_path=str(CHARUCO_AS_GROUND_PLANE_PNG),
        tab_order=0,
        tab_title="v1.7.0 Release Notes",
        content_title="FreeMoCap v1.7.0 - Ground Plane Calibration!",
        content_subtitle="✨ New Feature: Ground Plane Calibration (and new board definitions)",
        content_html=f"""
<style>
    p {{ margin: 5px 0; }}
    ul, ol {{ margin: 10px 0 10px 20px; }}
    li {{ margin: 3px 0; }}
    a {{ color: #4fc3f7; text-decoration: none; }}
    b {{ font-weight: bold; }}
    em {{ font-style: italic; }}
    .emphasis {{ font-weight: bold; }}
    .note {{ margin: 10px 0; padding: 8px; background-color: #884; }}
</style>


We have (finally!) added a new feature to allow you to define the ground plane of your capture volume during calibration
based on the initial position of a ChArUco board.
</p>

<p>
    <b>How to use it:</b>
</p>
<ol>
    <li>Check the <span class="emphasis">"Use board position as origin"</span> option before calibration</li>
    <li>Start your calibration recording with the board flat on the ground (visible to as many cameras as possible) for a few seconds</li>
    <li>Continue calibration as normal - that's it!</li>
</ol>
<p>
    This new feature automatically aligns your 3D Capture Volume to the detected board position, ensuring:
</p>
<ul>
    <li>The origin is at the charco corner #0</li>
    <li>The X+ axis points along the board's SHORT axis</li>
    <li>The Y+ axis points along the board's LONG axis</li>
    <li>The Z+ axis points UPWARDS normal to the board (XxY)</li>
</ul>

<p>
    Previously, the reference frame resulting from our customized  <a href="https://github.com/lambdaloop/aniposelib">anipose</a>
    based calibration method was defined based on the 6DoF position of the first camera,
    and we defined the floor post-hoc in each recording based on detected foot location.
</p>

<p>
    This process could fail if the feet weren't detected well, resulting the data returning a random-ish orientation.
    (NOTE:
    You can correct this kind of error by adjusting the position of the recording parent Empty in the generated
    `[recording_name].blend` Blender scene).
</p>

<p>
    The new calibration method sets the capture volume orientation at the level of <em>CALIBRATION</em> file, which keeps the reference frame
consistent across recordings.
</p>

<p class="note">
    <b>Note:</b> If ground plane calibration fails (board not visible or moving), the system automatically falls back
    to the standard calibration method.
</p>

<p>
For detailed instructions and troubleshooting, check out the  <a
        href="https://docs.freemocap.org/documentation/groundplane-calibration.html"> <em>Ground Plane Calibration Guide</em></a>.
</p>

<hr/>

<p>
    <em>🆕 New 5x3 ChArUco board definition </em>
</p>

<p>
In addition, our calibration process now supports a new 5x3 ChArUco board (5 rows, 3 columns)!
</p>

<p>
This definition will print larger Aruco patterns than the original 7x5 pattern for a given paper size, which will make it
easier to calibrate larger spaces without needing to construct or print
a poster-sized board.
</p>

<p>
For details or to download high resolution images board images, see  <a href="https://docs.freemocap.org/documentation/multi-camera-calibration.html#charuco-board-types"><em>Preparing the Charuco Board</em></a>.
</p>

<hr/>

<p>
For additional details about what's new in v1.7.0 - See <a
        href="https://github.com/freemocap/freemocap/releases/tag/v1.7.0">the official release page</a>
</p>

<p>
(You can always access these release notes from the <b>Help</b> menu.)
</p>
        """,
    )



def get_v160_release_notes() -> ReleaseNoteContent:
    """Return the release notes for v1.6.0."""

    return ReleaseNoteContent(
        latest=False,  # No longer the latest
        tab_title="v1.6.0 Data Scaling",
        content_title="FreeMoCap v1.6.0 - Data Scaling improvement!",
        content_html="""
            <html>
            <style>
            a {{ color: #ccc; text-decoration: none; font-weight: 500; }}
            .emphasis {{ color: #aaa; font-weight: bold; }}
            </style>
            <body>
            <p>So, remember last time when we said we were going to add a <a href="https://github.com/freemocap/freemocap/pull/676"> set of comprehensive quality assurance diagnostics </a> to ensure monotonically increasing data quality?
            <br/><br/>

            Well, we did that and immediately discovered a bug in our calibration/reconstruction pipeline that has apparently been causing a ~10-15% scaling offset to our data (i.e. so measured limb segment lengths would be ~85-115% of their real-world lengths)
            <br/><br/>
           Good news is that we fixed it, so our data should be more accurately scaled to real-world units! We call that progress 😌
            <br/><br/>
            If your application requires empirical accuracy, we recommend reprocessing any critical data with the latest version of FreeMoCap to ensure the highest quality results.
            <br/>
            <br>
            See  <a href="https://github.com/freemocap/freemocap/pull/681">Issue #681</a> for a full run down on the code sleuthing and thread pulling that led to this fix.
            <br>
            --
            <br>
            For additional details about what's new in v1.6.3 - See <a href="https://github.com/freemocap/freemocap/releases/tag/v1.6.3">the official release page </a>
            <br/><br/>
            (You can always access these release notes from the <b>Help</b> menu.)

            </body>
            </html>
        """,
        logo_path=SKELLY_HEART_EYES_PNG,
        tab_order=1,  # Now second
    )


def get_v154_release_notes() -> ReleaseNoteContent:
    """Return the release notes for v1.5.4 (Butterworth fix)."""

    return ReleaseNoteContent(
        tab_title="v1.5.4 Butterworth Filter Fix",
        content_title="Butterworth Filter Fix in v1.5.4",
        content_html="""
            <html>
            <style>
            a {{ color: #ccc; text-decoration: none; font-weight: 500; }}
            .emphasis {{ color: #aaa; font-weight: bold; }}
            </style>
            <body>
            <p style="font-size: 18px; font-weight: bold; color: #f5a; margin-bottom: 15px;">
                Whoops!!
            </p>
            <p style="font-size: 16px; font-weight: semibold; color: #fc8;   margin-bottom: 15px;">
                Possible data Quality Regression in versions 1.4.7-1.5.3
            </p>

            <p>We identified and fixed a bug in <b>v1.4.7-v1.5.3 (10 Oct 2024 - 10 Mar 2025)</b> that caused the pipeline to Butterworth filtering during processing (<a href="https://github.com/freemocap/freemocap/pull/675">Bugfix PR</a>).
            Recordings from these versions may have increased noise/jitter/shakiness in the final keypoint trajectories.
            <br/><br/>
            Based on your application, the difference may or may not be noticeable. It is most likely to affect users who's applications focus on fine grained trajectories of the hands and limbs (especially for scientific analysis)
            <br/><br/>
            <b>We recommend reprocessing any critical data collected during this period with the latest version of FreeMoCap to ensure the highest quality results.</b>
            <br/><br/>
             You may also filter the data in Blender (see <a href="https://www.youtube.com/watch?v=33OhM5xFUlg">this tutorial Flux Renders</a>)
            <br/>
            --
            <br>
            In preparation for the release of FreeMoCap v2.0 (optimistically Summer 2025), we are implementing a <a href="https://github.com/freemocap/freemocap/pull/676"> set of comprehensive quality assurance diagnostics </a>to ensure that the quality of our output is strictly monotonic across future versions.

            <p style="font-size: 13px; margin-top: 20px; color: #7f8c8d;">
            Thanks to  (<a href="https://discord.com/channels/760487252379041812/760489602917466133/1346487740568440983">@larap for reporting</a>), and to the rest of the freemocap community for their help in developing this project.
            </p>
            </body>
            </html>
        """,
        logo_path=SKELLY_SWEAT_PNG,
        tab_order=2,  # Now third
    )


def get_older_versions_content() -> ReleaseNoteContent:
    """Return the content for older versions tab."""
    return ReleaseNoteContent(
        tab_title="Older Versions",
        content_title="Previous Versions",
        content_html="""
        <p>For information about older versions, please visit our
        <a href='https://github.com/freemocap/freemocap/releases'>GitHub releases page</a>.</p>
        """,
        logo_path=None,
        tab_order=3,  # Now fourth
    )


def get_all_release_notes() -> list[ReleaseNoteContent]:
    """Return all release notes in the correct order."""
    release_notes = [
        get_v170_release_notes(),
        get_v160_release_notes(),
        get_v154_release_notes(),
        get_older_versions_content(),
    ]

    # Sort by tab_order
    return sorted(release_notes, key=lambda x: x.tab_order)