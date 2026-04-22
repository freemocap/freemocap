from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_content import ReleaseNoteContent
from freemocap.gui.qt.widgets.release_notes_dialogs.versions._image_paths import SKELLY_OUTLIER_REJECTION, \
    OUTLIER_REJECTION_UI_PNG

_HTML = """
<style>
    p { margin: 5px 0; }
    ul, ol { margin: 10px 0 10px 20px; }
    li { margin: 3px 0; }
    a { color: #94c4c7; text-decoration: none; }
    b { font-weight: bold; }
    em { font-style: italic; }
    .emphasis { font-weight: bold; }
    .note { margin: 10px 0; padding: 8px; background-color: #884; }
    .math {
        text-align: center;
        margin: 18px 0;
        font-style: italic;
        font-size: 20px;
        letter-spacing: 0.03em;
    }
</style>

<p>
    v1.8.0 adds an <b>optional</b> outlier-rejection step to the triangulation pipeline, which should greatly improve
    the reconstruction quality with 4+ camera systems!
    <br/>
    <br/>
    Note that it is set <b>OFF by default</b> in this release — We are pretty sure it will improve results in most
    cases, but because it touches the core processing pipeline we wanted to be careful about rolling it out. We will
    update these release notes when we switch it to <b>ON by default<b/> in a future (probably patch) version bump.
    <br/>
    <br/>
    If you have a 4+ camera set up (or even better, old recordings that didn't quite reconstruct like they should),
    please try processing with the new setting turned on and let us know how it goes on this tracking issue:
    <a href="https://github.com/freemocap/freemocap/issues/782">freemocap#782</a> or in the
    <a href="https://discord.gg/freemocap">FreeMoCap Discord</a> server.
</p>

<hr/>
<p>
    <b>How to use it — Check the box at
    <em>Process Data &gt; 3D Triangulation &gt; Use Outlier Rejection Method?</em>
    before processing data</b>
</p>
<p>
    We recommend using this method for any recording with 4+ cameras. For 3-camera recordings, this method may
    result in unstable reconstructions (because 2-camera triangulation can be shaky).
</p>
<p>
    For the method to have any effect, the number of cameras in your recording must be <em>greater than</em>
    <span class="emphasis">"Minimum Cameras for Triangulation"</span> (see below) — otherwise there are no subsets
    left to test.
</p>

<hr/>
<p><b>How it works — Rejects high-error camera-keypoint views during triangulation</b></p>
<p>
    <em>Reprojection error</em> is the standard way to measure triangulation quality: after computing a 3D
    point from multiple camera views, you "reproject" it back into each camera and measure how far it lands
    from the original 2D detection. A small error means that camera's view is consistent with the
    reconstruction; a large error means something was off — occlusion, a ghost skeleton, a bad detection.
</p>
<p>
    This step uses that signal to reject outlier views: if the mean reprojection error across all cameras
    exceeds a target threshold <em>&epsilon;<sub>target</sub></em>, the algorithm tests subsets of cameras formed by
    progressively dropping cameras (up to <em>maximum cameras to drop</em>). Each subset is triangulated
    independently and assigned a weight:
</p>
<p class="math">
    w = e<sup style="font-size:14px">&minus;5 &sdot; &epsilon; / &epsilon;<sub>target</sub></sup>
</p>
<ul style="margin-top:4px; margin-bottom:8px; font-size:13px; color:#b0b0b0;">
    <li><em>w</em> — weight assigned to a particular camera subset</li>
    <li><em>&epsilon;</em> — mean reprojection error (in pixels) for that subset</li>
    <li><em>&epsilon;<sub>target</sub></em> — the user-configurable target error threshold; subsets below this get weight &asymp; 1, subsets far above it get weight &asymp; 0</li>
    <li>The factor of 5 sets the sharpness of the exponential decay — a subset with error = &epsilon;<sub>target</sub> gets weight e<sup>&minus;5</sup> &asymp; 0.007 (nearly zero)</li>
</ul>
<p>
    Lower error means exponentially higher weight. The final 3D point is then a weighted average across all
    tested subsets:
</p>
<p class="math">
    p&#x302; &nbsp;=&nbsp; &Sigma;<sub style="font-size:13px">i</sub>(w<sub style="font-size:13px">i</sub> &sdot; p<sub style="font-size:13px">i</sub>) / &Sigma;<sub style="font-size:13px">i</sub>(w<sub style="font-size:13px">i</sub>)
</p>
<ul style="margin-top:4px; margin-bottom:8px; font-size:13px; color:#b0b0b0;">
    <li><em>p&#x302;</em> — the final estimated 3D point position</li>
    <li><em>p<sub>i</sub></em> — the 3D point triangulated from camera subset <em>i</em></li>
    <li><em>w<sub>i</sub></em> — the weight for subset <em>i</em> (from the formula above)</li>
    <li><em>&Sigma;</em> — sum over all tested camera subsets</li>
    <li>Dividing by <em>&Sigma;w<sub>i</sub></em> normalises the result so the weights don't need to sum to 1 themselves</li>
</ul>
<p>
    So well-behaved camera combinations dominate the result. This smooth blending avoids sharp frame-to-frame
    jumps when the "best" camera subset changes, which would otherwise introduce instability and shakiness
    in the reconstruction.
</p>
<p>
    More details on the <a href="https://docs.freemocap.org/documentation/reprojection-filtering.html"><em>Reprojection
    Filtering</em></a> docs page.
    <br/>
    See <a href="https://github.com/freemocap/freemocap/pull/758">PR #758</a> for the code.
</p>

<hr/>

<p><b>Why it matters — Allows for higher camera count (4+) recordings</b></p>
<p>
    Previously, adding more cameras to a rig ran into a "poison pill" problem: the more cameras you had, the higher the
    odds that at least one of them would pick up a bad track (spooky <em>ghost skeletons</em> 💀👻) and contaminate the
    3D reconstruction. This effectively capped the number of cameras that were useful in practice. With outlier
    rejection, bad views are automatically identified and excluded on a per-point basis, making higher camera count
    reconstruction more robust.
</p>

<hr/>



<p><b>&#x1F195; Also new: <em>Minimum Cameras for Triangulation</em> (a top-level option)</b></p>
<p>
    We also added a <span class="emphasis">"Minimum Cameras for Triangulation"</span> option to the
    <span class="emphasis">3D Triangulation Methods</span> panel with a default value of <b>3</b>.
    It now applies to <em>both</em> the simple triangulation path <em>and</em> the outlier-rejection path.
    Any point with fewer valid 2D detections than this threshold will be left out of the 3D output.
</p>
<p>
    If you set this value higher than the number of cameras in your recording (e.g. <b>min=3</b> on a 2-camera rig),
    FreeMoCap will emit a warning in the logs and <b>automatically adjust the value down to the number of cameras
    available</b> so processing still runs.
</p>

<hr/>

<p><b>&#x1F389; Contributor shout-out</b></p>
<p>
    This feature was contributed by <a href="https://github.com/ajc27-git">ajc27</a>, a long-time member of the
    FreeMoCap community who has done great work on the Blender output pipeline and has been a consistent, generous
    presence helping folks in our Discord server. This is their first contribution to touch the <em>core reconstruction
    pipeline</em> — which is worth celebrating!
</p>

<hr/>

<p>
    For additional details about what's new in v1.8.0 — see
    <a href="https://github.com/freemocap/freemocap/releases/tag/v1.8.0">the official release page</a>.
</p>
<p>(You can always access these release notes from the <b>Help</b> menu.)</p>
"""


def get_v180_release_notes() -> ReleaseNoteContent:
    return ReleaseNoteContent(
        latest=True,
        logo_path=SKELLY_OUTLIER_REJECTION,
        image_path=OUTLIER_REJECTION_UI_PNG,
        tab_order=0,
        tab_title="v1.8.0 Reprojection Outlier Rejection",
        content_title="FreeMoCap v1.8.0 - Outlier rejection",
        content_subtitle="✨ New Feature: Outlier rejection during triangulation",
        content_html=_HTML,
    )
