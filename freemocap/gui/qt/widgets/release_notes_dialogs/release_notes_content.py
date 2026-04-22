import logging
from dataclasses import dataclass
from pathlib import Path

from freemocap.system.paths_and_filenames.file_and_folder_names import PATH_TO_FREEMOCAP_LOGO_SVG

logger = logging.getLogger(__name__)

SKELLY_LOGO_BASE_SVG_FILENAME = "freemocap-logo-black-border.svg"
SKELLY_SWEAT_PNG = PATH_TO_FREEMOCAP_LOGO_SVG.replace(
    SKELLY_LOGO_BASE_SVG_FILENAME, "skelly-sweat.png")
SKELLY_HEART_EYES_PNG = PATH_TO_FREEMOCAP_LOGO_SVG.replace(
    SKELLY_LOGO_BASE_SVG_FILENAME, "skelly-heart-eyes.png")
SKELLY_THIS_WAY_UP_PNG = PATH_TO_FREEMOCAP_LOGO_SVG.replace(
    SKELLY_LOGO_BASE_SVG_FILENAME, "skelly-this-way-up.png")
SKELLY_OUTLIER_REJECTION = PATH_TO_FREEMOCAP_LOGO_SVG.replace(
    SKELLY_LOGO_BASE_SVG_FILENAME, "skelly-outlier-rejection.png")

CHARUCO_AS_GROUND_PLANE_PNG = Path(PATH_TO_FREEMOCAP_LOGO_SVG).parent.parent / "charuco/charuco_as_groundplane.png"
OUTLIER_REJECTION_UI_PNG = str(Path(PATH_TO_FREEMOCAP_LOGO_SVG).parent.parent / "notes/outlier_rejection_ui.png")

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


def get_v180_release_notes() -> ReleaseNoteContent:
    """Return the release notes for v1.7.0."""

    return ReleaseNoteContent(
        latest=True,
        logo_path=SKELLY_OUTLIER_REJECTION,
        image_path=OUTLIER_REJECTION_UI_PNG,
        tab_order=0,
        tab_title="v1.8.0 Reprojection Outlier Rejection",
        content_title="FreeMoCap v1.8.0 - Outlier rejection",
        content_subtitle="✨ New Feature: Outlier rejection during triangulation",
        content_html="""
<style>
    p {{ margin: 5px 0; }}
    ul, ol {{ margin: 10px 0 10px 20px; }}
    li {{ margin: 3px 0; }}
    a {{ color: #94c4c7; text-decoration: none; }}
    b {{ font-weight: bold; }}
    em {{ font-style: italic; }}
    .emphasis {{ font-weight: bold; }}
    .note {{ margin: 10px 0; padding: 8px; background-color: #884; }}
</style>

<p>
v1.8.0 adds an <b>optional</b> outlier-rejection step to the triangulation pipeline, which should greatly improve the reconstruction quality with 4+ camera systems!

We are pretty sure it will be an improvement in most cases, but to safe it is set <b>off by default</b> in this release — we want the community to kick the tires before we consider flipping the switch.
</p>




<hr/>

<p>
    <b>What it does</b>
</p>
<p>
When triangulating a 3D point, the method checks how well the reconstructed point projects back into each camera view. Points with high reprojection error are re-triangulated using a subset of cameras — an exponential weighting scheme scores candidate subsets by their reprojection error and selects the combination that minimizes error across the remaining views. Full details on the <a href="https://docs.freemocap.org/documentation/reprojection-filtering.html"><em>Reprojection Filtering</em></a> docs page.
</p>

<hr/>

<p>
    <b>Why it matters</b>
</p>
<p>
Previously, adding more cameras to a rig ran into a "poison pill" problem: the more cameras you had, the higher the odds that at least one of them would pick up a bad track (a so-called <em>ghost skeleton</em>) and contaminate the 3D reconstruction. This effectively capped the number of cameras that were useful in practice. With outlier rejection, bad views can be identified and excluded on a per-point basis, making <b>high-camera-count rigs</b> viable for more robust and ambitious recordings.
</p>

<hr/>

<p>
    <b>How to use it</b>
</p>
<ul>
    <li>In the <span class="emphasis">3D Triangulation Methods</span> panel, open the <span class="emphasis">Outlier Rejection</span> sub-group and enable <span class="emphasis">"Use Outlier Rejection Method?"</span> before processing.</li>
    <li><b>Recommended</b> if you have <b>4 or more cameras</b>.</li>
    <li>For the method to have any effect, the number of cameras in your recording must be <em>greater than</em> <span class="emphasis">"Minimum Cameras for Triangulation"</span> (see below) — otherwise there are no subsets left to test. With a 3-camera rig you'd need to lower the minimum to 2, which can introduce instability/wobble in the reconstruction.</li>
</ul>

<p class="note">
    <b>Heads up:</b> This is a significant shift from the previous triangulation logic, so it ships <b>off by default</b>. If it works well for you (or doesn't!), we want to hear about it.
</p>

<hr/>

<p>
    <b>🆕 Also new: <em>Minimum Cameras for Triangulation</em> (a top-level option)</b>
</p>
<p>
While we were in the neighborhood, we promoted <span class="emphasis">"Minimum Cameras for Triangulation"</span> out of the outlier-rejection sub-group and up to the top level of the <span class="emphasis">3D Triangulation Methods</span> panel. It now applies to <em>both</em> the simple triangulation path <em>and</em> the outlier-rejection path. Any point with fewer valid 2D detections than this threshold will be left as NaN in the 3D output — which is generally what you want, since reconstructions from too few cameras are noisy and unreliable.
</p>
<p>
If you set this value higher than the number of cameras in your recording (e.g. <b>min=3</b> on a 2-camera rig), FreeMoCap will emit a warning in the logs and <b>automatically clamp the value down to the number of cameras available</b> so processing still runs. The hard floor is 2 (triangulation from a single camera isn't possible). This means you can leave a sensible default in place and not have to babysit the setting across rigs of different sizes.
</p>

<hr/>

<p>
    <b>Tell us how it went</b>
</p>
<p>
Please share your results — good, bad, or weird — on the <a href="https://discord.gg/freemocap">FreeMoCap Discord</a> or in the tracking issue <a href="https://github.com/freemocap/freemocap/issues/782">freemocap#782</a>. Your feedback will decide whether we make outlier rejection the default in a future release. These release notes will be updated if/when that happens.
</p>

<hr/>
<p>
    <b>🎉 Contributor shout-out</b>
</p>
<p>
This feature was contributed by <a href="https://github.com/ajc27-git">ajc27</a>, a long-time member of the FreeMoCap community who has done great work on the Blender output pipeline and has been a consistent, generous presence helping folks in our Discord server. This is their first contribution to touch the <em>core reconstruction pipeline</em> — which is worth celebrating!. See <a href="https://github.com/freemocap/freemocap/pull/758">PR #758</a> for the code.
</p>
<hr/>

<p>
For additional details about what's new in v1.8.0 - see <a
        href="https://github.com/freemocap/freemocap/releases/tag/v1.8.0">the official release page</a>.
</p>

<p>
(You can always access these release notes from the <b>Help</b> menu.)
</p>
        """,
    )


def get_v170_release_notes() -> ReleaseNoteContent:
    """Return the release notes for v1.7.0."""

    return ReleaseNoteContent(
        latest=True,
        logo_path=SKELLY_THIS_WAY_UP_PNG,  # Using the "this way up" logo since it's about orientation
        image_path=str(CHARUCO_AS_GROUND_PLANE_PNG),
        tab_order=0,
        tab_title="v1.7.0 Ground Plane Calibration",
        content_title="FreeMoCap v1.7.0 - Ground Plane Calibration!",
        content_subtitle="✨ New Feature: Ground Plane Calibration (and new board definitions)",
        content_html="""
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
        get_v180_release_notes(),
        get_v170_release_notes(),
        get_v160_release_notes(),
        get_v154_release_notes(),
        get_older_versions_content(),
    ]

    # Sort by tab_order
    return sorted(release_notes, key=lambda x: x.tab_order)
