"""Publish posthoc observations with SkellyCam timing into the canonical store."""

from collections.abc import Iterator
from dataclasses import replace
from freemocap.core.pipeline.posthoc.execution_inputs import CameraExecutionInputs
from freemocap.core.recording.channel_series import SeriesSampling
from pathlib import Path

import pyarrow as pa
from skellycam.core.timestamps.recording_timing_reader import (
    TimingMethod,
    TimingFileKind,
)
from freemocap.core.recording.observation_recording_models import (
    ObservationRecordingRequest,
    CameraRecordingDefinition,
    ImageReference,
    CameraObservationChannels,
    GroupTimingDefinition,
    TimingSampleName,
    create_timing_channel,
)


from skellycam.core.timestamps.recording_timing_reader import (
    read_recording_timing,
    resolve_camera_timing,
)


from freemocap.core.pipeline.posthoc.processing_request import (
    ProcessingRequest,
    ProcessingStage,
)
from freemocap.core.pipeline.posthoc.stage_execution_plan import (
    build_execution_plan,
    retained_run,
)

from freemocap.core.recording.observation_samples import (
    TimedObservation,
    observation_batches,
    timing_batches,
)
from freemocap.core.recording.recording_checkpoint import publish_checkpoint
from freemocap.core.recording.recording_metadata import (
    Channel,
    RecordingMetadata,
    RunDescriptor,
    SensorGroup,
    Source,
)
from freemocap.core.recording.recording_reader import read_metadata
from freemocap.core.recording.recording_writer import (
    publish_recording,
    recording_write_lock,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def publish_posthoc_observations(
    request: ObservationRecordingRequest,
) -> RecordingMetadata:
    """Publish timing and detection in run 0, invalidating dependent saved computations.

    Input videos are already synchronized; an absent timing sidecar uses video frame zero
    as time zero. Per-camera recorded offsets are preserved. Other runs/groups survive.
    Completion checkpoints are deferred until input-signature construction is integrated.
    """
    frame_numbers = request.group.frame_numbers
    channels: list[Channel] = []
    sources = {request.tracker.name: request.tracker.to_source()}
    references: dict[str, dict[str, object]] = {}
    camera_times: dict[str, tuple[float, ...]] = {}
    camera_channels: dict[str, CameraObservationChannels] = {}
    for camera, video in request.group.videos.items():
        if frame_numbers != tuple(range(video.start_frame, video.end_frame)):
            raise ValueError("Observations must cover the selected video frame range")
        timeline = resolve_camera_timing(
            path=Path(
                request.recording.camera_timestamps_file_path_from_camera_id(camera)
            ),
            frame_count=video.frame_count,
            fps=video.fps,
            offset_s=0.0,
        )
        camera_times[camera] = tuple(
            timeline.timestamps_s[frame] for frame in frame_numbers
        )
        camera_definition = CameraRecordingDefinition(
            camera_id=camera,
            timing_method=timeline.method,
            nominal_fps=video.fps,
            inferred_offset_s=0.0,
        )
        image = ImageReference(camera_id=camera, width=video.width, height=video.height)
        sources[camera_definition.source_name] = camera_definition.to_source()
        references[image.name] = image.model_dump(mode="json")
        for index, frame in enumerate(request.group.frames):
            if frame[camera].frame_number != frame_numbers[index]:
                raise ValueError("Camera observations disagree on group frame number")
            if frame[camera].image_size != (video.height, video.width):
                raise ValueError(
                    "Observation image coordinates do not match the video dimensions"
                )
        camera_channels[camera] = CameraObservationChannels.create(
            request=request, image=image
        )
        channels.extend(
            (camera_channels[camera].overlay, camera_channels[camera].capture)
        )
    group_path = Path(request.recording.timestamp_file_path)
    if group_path.exists():
        group_timing = read_recording_timing(
            path=group_path, kind=TimingFileKind.MULTIFRAME
        )
        synchronized = tuple(group_timing[frame] for frame in frame_numbers)
        group_method = TimingMethod.RECORDED
    else:
        synchronized = tuple(
            sum(times[index] for times in camera_times.values())
            / len(request.group.videos)
            for index in range(len(frame_numbers))
        )
        group_method = TimingMethod.MEAN_CAMERA_TIMES
    group_source = f"timing:{request.group.name}"
    sources[group_source] = GroupTimingDefinition(method=group_method).to_source()
    group_channel = create_timing_channel(
        group=request.group.name,
        source=group_source,
        name=TimingSampleName.SYNCHRONIZED,
    )
    channels.append(group_channel)
    for series in request.spatial_series:
        channels.append(series.definition.to_channel())
        references[series.definition.reference.name] = (
            series.definition.reference.model_dump(mode="json")
        )
    for reconstruction in request.reconstructions:
        if reconstruction.definition.model_id in sources:
            raise ValueError(
                "Reconstruction source collides with another recording source"
            )
        sources[reconstruction.definition.model_id] = (
            reconstruction.definition.to_source()
        )
        references[reconstruction.reference.name] = reconstruction.reference.model_dump(
            mode="json"
        )
        channels.extend(reconstruction.channels())
    run = RunDescriptor(
        scale_fits=tuple(item.to_scale_fit() for item in request.reconstructions),
        camera_geometry={request.group.name: request.camera_geometry},
        sensor_groups={
            request.group.name: SensorGroup(
                clock_description="recording-relative seconds; timing method declared per source",
                sample_count=len(frame_numbers),
            )
        },
        sources=sources,
        reference_frames=references,
        models={},
        processing={},
        channels=tuple(channels),
    )

    def batches() -> Iterator[pa.RecordBatch]:
        for reconstruction in request.reconstructions:
            for series in reconstruction.series():
                yield from series.batches(
                    SeriesSampling(
                        frame_numbers=frame_numbers, timestamps_s=synchronized, run_id=0
                    )
                )
        for series in request.spatial_series:
            yield from series.batches(
                SeriesSampling(
                    frame_numbers=frame_numbers,
                    timestamps_s=synchronized,
                    run_id=0,
                )
            )
        for camera in request.group.videos:
            yield from observation_batches(
                samples=(
                    TimedObservation(
                        observation=frame[camera], capture_timestamp_s=timestamp
                    )
                    for frame, timestamp in zip(
                        request.group.frames, camera_times[camera], strict=True
                    )
                ),
                channel=camera_channels[camera].overlay,
                run_id=0,
                batch_size=65536,
            )
            yield from timing_batches(
                samples=zip(frame_numbers, camera_times[camera], strict=True),
                channel=camera_channels[camera].capture,
                run_id=0,
                batch_size=65536,
            )
        yield from timing_batches(
            samples=zip(frame_numbers, synchronized, strict=True),
            channel=group_channel,
            run_id=0,
            batch_size=65536,
        )

    structure = RecordingStructure(
        base_directory=Path(request.recording.recording_directory),
        recording_name=request.recording.recording_name,
    )
    with recording_write_lock(structure=structure):
        if not structure.data_parquet_path.exists():
            metadata = RecordingMetadata(
                recording_id=structure.recording_name, selected_run_id=0, runs={0: run}
            )
            publish_recording(structure=structure, metadata=metadata, batches=batches())
            return metadata
        metadata = read_metadata(path=structure.data_parquet_path)
        plan = build_execution_plan(
            inputs={
                request.group.name: CameraExecutionInputs(
                    camera_ids=tuple(request.group.videos),
                    geometry=request.camera_geometry,
                )
            },
            request=ProcessingRequest(
                sensor_groups=(request.group.name,),
                start_stage=ProcessingStage.TIMING,
                stop_stage=ProcessingStage.OBSERVATIONS,
            ),
            metadata=metadata,
            signatures={request.group.name: {}},
        )
        if request.spatial_series:
            plan = replace(plan, execute=(*plan.execute, ProcessingStage.TRIANGULATION))
        if request.reconstructions:
            plan = replace(
                plan,
                execute=(
                    *plan.execute,
                    ProcessingStage.SCALE_FIT,
                    ProcessingStage.RECONSTRUCTION,
                ),
            )
        retained = retained_run(base=metadata.runs[0], plan=plan)
        if (
            retained.sensor_groups[request.group.name]
            != run.sensor_groups[request.group.name]
        ):
            raise ValueError(
                "Observation overwrite cannot change the saved sample grid"
            )
        result = RunDescriptor(
            scale_fits=(*retained.scale_fits, *run.scale_fits),
            camera_geometry={**retained.camera_geometry, **run.camera_geometry},
            sensor_groups=retained.sensor_groups,
            sources={**retained.sources, **sources},
            reference_frames={**retained.reference_frames, **references},
            models=retained.models,
            processing=retained.processing,
            channels=(*retained.channels, *channels),
            static_channels=retained.static_channels,
            checkpoints=retained.checkpoints,
        )
        return publish_checkpoint(
            structure=structure,
            metadata=metadata,
            plan=plan,
            result=result,
            computed_batches=batches(),
        )
