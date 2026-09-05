"""Static channel views derived from the single stored scientific scale fit."""

from collections.abc import Iterator

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.recording_metadata import (
    Channel,
    RunDescriptor,
    StaticChannel,
)
from freemocap.core.recording.sample_conventions import SampleComponent
from freemocap.core.types.channel_kind import ChannelKind


def scale_fit_channels(run: RunDescriptor) -> Iterator[StaticChannel]:
    for saved in run.scale_fits:
        if saved.fit is None:
            continue
        for kind, component, measurements in (
            (
                ChannelKind.MODEL_SCALE,
                SampleComponent.SCALE,
                {run.models[saved.source].scale_reference_name: saved.fit.fitted_scale},
            ),
            (
                ChannelKind.SEGMENT_SCALES,
                SampleComponent.SCALE,
                saved.fit.segment_scales,
            ),
            (
                ChannelKind.SEGMENT_LENGTHS,
                SampleComponent.LENGTH,
                saved.fit.segment_lengths,
            ),
        ):
            yield StaticChannel(
                channel=Channel(
                    sensor_group=saved.sensor_group,
                    source=saved.source,
                    reference_frame=saved.reference_frame,
                    kind=kind,
                    names=tuple(measurements),
                    components={component: saved.units},
                    stage=ProcessingStage.SCALE_FIT,
                ),
                values={
                    name: {component: value} for name, value in measurements.items()
                },
            )
