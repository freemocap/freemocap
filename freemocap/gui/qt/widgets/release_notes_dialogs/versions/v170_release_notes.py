from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_content import ReleaseNoteContent
from freemocap.gui.qt.widgets.release_notes_dialogs.versions._image_paths import SKELLY_THIS_WAY_UP_PNG, CHARUCO_AS_GROUND_PLANE_PNG

_HTML = """
<style>
    p { margin: 5px 0; }
    ul, ol { margin: 10px 0 10px 20px; }
    li { margin: 3px 0; }
    a { color: #4fc3f7; text-decoration: none; }
    b { font-weight: bold; }
    em { font-style: italic; }
    .emphasis { font-weight: bold; }
    .note { margin: 10px 0; padding: 8px; background-color: #884; }
</style>

<p>
    We have (finally!) added a new feature to allow you to define the ground plane of your capture volume during
    calibration based on the initial position of a ChArUco board.
</p>

<p><b>How to use it:</b></p>
<ol>
    <li>Check the <span class="emphasis">"Use board position as origin"</span> option before calibration</li>
    <li>Start your calibration recording with the board flat on the ground (visible to as many cameras as possible) for a few seconds</li>
    <li>Continue calibration as normal — that's it!</li>
</ol>
<p>This new feature automatically aligns your 3D Capture Volume to the detected board position, ensuring:</p>
<ul>
    <li>The origin is at the charuco corner #0</li>
    <li>The X+ axis points along the board's SHORT axis</li>
    <li>The Y+ axis points along the board's LONG axis</li>
    <li>The Z+ axis points UPWARDS normal to the board (X&times;Y)</li>
</ul>

<p>
    Previously, the reference frame resulting from our customized
    <a href="https://github.com/lambdaloop/aniposelib">anipose</a>-based calibration method was defined based on
    the 6DoF position of the first camera, and we defined the floor post-hoc in each recording based on detected
    foot location.
</p>
<p>
    This process could fail if the feet weren't detected well, resulting in the data returning a random-ish
    orientation. (NOTE: You can correct this kind of error by adjusting the position of the recording parent
    Empty in the generated <code>[recording_name].blend</code> Blender scene).
</p>
<p>
    The new calibration method sets the capture volume orientation at the level of the <em>CALIBRATION</em>
    file, which keeps the reference frame consistent across recordings.
</p>

<p class="note">
    <b>Note:</b> If ground plane calibration fails (board not visible or moving), the system automatically falls
    back to the standard calibration method.
</p>

<p>
    For detailed instructions and troubleshooting, check out the
    <a href="https://docs.freemocap.org/documentation/groundplane-calibration.html"><em>Ground Plane Calibration Guide</em></a>.
</p>

<hr/>

<p><em>&#x1F195; New 5x3 ChArUco board definition</em></p>
<p>
    Our calibration process now supports a new 5x3 ChArUco board (5 rows, 3 columns)!
    This definition will print larger Aruco patterns than the original 7x5 pattern for a given paper size,
    making it easier to calibrate larger spaces without needing to construct or print a poster-sized board.
</p>
<p>
    For details or to download high-resolution board images, see
    <a href="https://docs.freemocap.org/documentation/multi-camera-calibration.html#charuco-board-types"><em>Preparing the Charuco Board</em></a>.
</p>

<hr/>

<p>
    For additional details about what's new in v1.7.0 — see
    <a href="https://github.com/freemocap/freemocap/releases/tag/v1.7.0">the official release page</a>.
</p>
<p>(You can always access these release notes from the <b>Help</b> menu.)</p>
"""


def get_v170_release_notes() -> ReleaseNoteContent:
    return ReleaseNoteContent(
        latest=False,
        logo_path=SKELLY_THIS_WAY_UP_PNG,
        image_path=CHARUCO_AS_GROUND_PLANE_PNG,
        tab_order=1,
        tab_title="v1.7.0 Ground Plane Calibration",
        content_title="FreeMoCap v1.7.0 - Ground Plane Calibration!",
        content_subtitle="✨ New Feature: Ground Plane Calibration (and new board definitions)",
        content_html=_HTML,
    )
