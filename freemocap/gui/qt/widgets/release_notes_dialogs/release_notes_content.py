from dataclasses import dataclass
from typing import Optional


@dataclass
class ReleaseNoteContent:
    """Data class to hold content for a release note tab."""
    latest: bool = False
    tab_title: str
    content_title: str
    content_html: str
    logo_path: Optional[str] = None
    tab_order: int = 0  # Lower numbers appear first


def get_v155_release_notes() -> ReleaseNoteContent:
    """Return the release notes for v1.5.5."""
    from freemocap.system.paths_and_filenames.file_and_folder_names import PATH_TO_FREEMOCAP_LOGO_SVG
    
    return ReleaseNoteContent(
        latest=True,
        tab_title="v1.5.5 Release Notes",
        content_title="FreeMoCap v1.5.5 Release Notes",
        content_html="""
        <p>Blah!:</p>
        
        <ul>
            <li><span class="feature">Blah1:</span> New feature that does something amazing</li>
            <li><span class="feature">Blah2:</span> Another feature that improves performance</li>
            <li><span class="feature">Blah3:</span> Bug fixes and improvements</li>
        </ul>
        
        <p>Check out our <a href="https://github.com/freemocap/freemocap/releases">release notes</a> for full details and our 
        <a href="https://freemocap.org/tutorial">tutorials</a> to get started with the new features.</p>
        
        <p style="font-size: 13px; margin-top: 20px;">
        Thank you to all our contributors and users for your continued support!
        </p>
        """,
        logo_path=PATH_TO_FREEMOCAP_LOGO_SVG,
        tab_order=0
    )


def get_v154_release_notes() -> ReleaseNoteContent:
    """Return the release notes for v1.5.4 (Butterworth fix)."""
    from freemocap.system.paths_and_filenames.file_and_folder_names import PATH_TO_FREEMOCAP_LOGO_SVG
    
    # Path to the skelly sweat image
    SKELLY_SWEAT_SVG = PATH_TO_FREEMOCAP_LOGO_SVG.replace("freemocap-logo-black-border.svg", "skelly-sweat.png")
    
    return ReleaseNoteContent(
        tab_title="v1.5.4 Data Quality Fix",
        content_title="Data Quality Fix in v1.5.4",
        content_html="""
        <p style="font-size: 16px; font-weight: semibold; margin-bottom: 15px;">
            Butterworth Filtering Bug Fixed
        </p>

        <p>We identified and fixed a bug in <b>v1.4.7-v1.5.3 (10 Oct 2024 - 10 Mar 2025)</b> that caused the pipeline to skip Butterworth filtering during processing (<a href="https://github.com/freemocap/freemocap/pull/675">Bugfix PR</a>).
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

        <p style="font-size: 13px; margin-top: 20px;">
        Thanks to  (<a href="https://discord.com/channels/760487252379041812/760489602917466133/1346487740568440983">@larap for reporting</a>), and to the rest of the freemocap community for their help in developing this project.
        </p>
        """,
        logo_path=SKELLY_SWEAT_SVG,
        tab_order=1
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
        tab_order=2
    )


def get_all_release_notes() -> list[ReleaseNoteContent]:
    """Return all release notes in the correct order."""
    release_notes = [
        get_v155_release_notes(),
        get_v154_release_notes(),
        get_older_versions_content(),
    ]
    
    # Sort by tab_order
    return sorted(release_notes, key=lambda x: x.tab_order)