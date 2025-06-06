from dataclasses import dataclass

from freemocap.system.paths_and_filenames.file_and_folder_names import PATH_TO_FREEMOCAP_LOGO_SVG

SKELLY_SWEAT_PNG = PATH_TO_FREEMOCAP_LOGO_SVG.replace("freemocap-logo-black-border.svg", "skelly-sweat.png")
SKELLY_HEART_EYES_PNG = PATH_TO_FREEMOCAP_LOGO_SVG.replace("freemocap-logo-black-border.svg", "skelly-heart-eyes.png")


@dataclass
class ReleaseNoteContent:
    """Data class to hold content for a release note tab."""

    tab_title: str
    content_title: str
    content_html: str
    logo_path: str | None = None
    tab_order: int = 0  # Lower numbers appear first
    latest: bool = False


def get_v160_release_notes() -> ReleaseNoteContent:
    """Return the release notes for v1.6.0."""

    return ReleaseNoteContent(
        latest=True,
        tab_title="v1.6.0 Release Notes",
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
            For additional details about what's new in v1.6.0 - See <a href="https://github.com/freemocap/freemocap/tree/v1.6.0">the official release page </a>
            <br/><br/>
            (You can always access these release notes from the <b>Help</b> menu.)

            </body>
            </html>
        """,
        logo_path=SKELLY_HEART_EYES_PNG,
        tab_order=0,
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
        tab_order=1,
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
        tab_order=2,
    )


def get_all_release_notes() -> list[ReleaseNoteContent]:
    """Return all release notes in the correct order."""
    release_notes = [
        get_v160_release_notes(),
        get_v154_release_notes(),
        get_older_versions_content(),
    ]

    # Sort by tab_order
    return sorted(release_notes, key=lambda x: x.tab_order)
