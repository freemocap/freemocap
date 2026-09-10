"""Encode triangulator measurements on the recording's synchronized frame grid."""

from collections.abc import Iterator

import numpy as np

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import (
    NamedReprojectionDiagnostics,
)
from freemocap.core.types.channel_kind import ChannelKind


def reprojection_series(
    *, diagnostics: NamedReprojectionDiagnostics, sensor_group: str
) -> Iterator[ChannelSeries]:
    values = diagnostics.values
    for index, camera in enumerate(diagnostics.source_ids):
        for kind, components, data in (
            (
                ChannelKind.REPROJECTION_ERROR,
                {"error": "px" if values.units == "pixels" else "1"},
                values.errors[index, ..., None],
            ),
            (
                ChannelKind.RECONSTRUCTION_COVERAGE,
                {"observed": "1", "reconstructed": "1"},
                np.stack(
                    (values.observed[index], values.reconstructed[index]), axis=-1
                ).astype(np.float64),
            ),
            (
                ChannelKind.TRIANGULATION_WEIGHTS,
                {"weight": "1"},
                values.weights[index, ..., None],
            ),
        ):
            yield ChannelSeries(
                channel=Channel(
                    sensor_group=sensor_group,
                    source=f"camera:{camera}",
                    reference_frame=f"camera:{camera}:image",
                    kind=kind,
                    names=diagnostics.point_names,
                    components=components,
                    stage=ProcessingStage.TRIANGULATION,
                ),
                values=data,
            )
