from dataclasses import dataclass
from skellyforge.core.data_tensors.channel_values import ChannelValues

from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import NamedReprojectionDiagnostics


@dataclass(slots=True, frozen=True)
class AngulationResult:
    """Dense spatial coordinates and optional reprojection errors for one frame.

    Both channels retain the authored entity axis and explicit entry presence.
    Invalid triangulations remain unavailable rows. Single-camera planar output
    has no reprojection-error channel because that quantity is undefined there.
    """

    points: ChannelValues
    errors_px: ChannelValues | None
    diagnostics: NamedReprojectionDiagnostics | None
