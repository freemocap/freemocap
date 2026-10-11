"""Recording graph composition using the application's existing scientific operations."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import multiprocessing
from uuid import uuid4

import cv2
import numpy as np
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellyforge.core.biomechanics.alignment_definition import AlignmentDefinition
from skellytracker.core import DetectionStageConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoDetectorConfig

from freemocap.core.pipeline.dataflow.definition import (
    CompiledGraph, DataContract, DataGranularity, GraphConnection, GraphDefinition,
    GraphNode, GraphPort, InputBindingRule, PortReference, compile_graph,
)
from freemocap.core.pipeline.dataflow.recording_executor import RecordingExecutionResult, execute_recording_graph
from freemocap.core.pipeline.dataflow.scientific_recording import ObservationCollection, triangulate_completed_observations, camera_assignment_metadata
from freemocap.core.pipeline.dataflow.tracker_adapter import SkellyTrackerAdapter
from freemocap.core.pipeline.dataflow.camera_join import ProducerOutcome
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.pipeline.posthoc.annotation_input import AnnotationInput
from freemocap.core.pipeline.posthoc.annotation_output import AnnotationOutputRequest, AnnotationVideoOutput
from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator
from freemocap.core.reconstruction.posthoc_filtering import prepare_recording_points
from freemocap.core.reconstruction.mocap_alignment import MocapAlignmentRequest, align_mocap_recording
from freemocap.core.reconstruction.posthoc_reconstruction import fit_skeletons_for_recording, reconstruct_skeletons_with_fits
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.result_processing.observation_inputs import (
    ObservationRecordingRequest, ObservationGroup, TrackerRecordingDefinition, DetectorRecordingDefinition,
)
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
from freemocap.core.recording.result_processing.provenance import ProvenanceContext
from freemocap.core.recording.sample_encoding.spatial_points import (
    SpatialReference, ReferenceAlignmentDescriptor, SpatialPointSeries, PointSeriesDefinition,
)
from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionRecording, ReconstructionSourceDefinition
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.skeletons.charuco_board_skeleton import build_charuco_board_bundle
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_update import CalibrationUpdateRequest
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import NamedReprojectionDiagnostics
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.tracking.tracker_definitions import MEDIAPIPE_WHOLEBODY_DEFINITION
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


RECORDING_INPUT_CONTRACTS = {
    "load_and_track": {},
    "observation_request": {"observations": "camera_observations"},
    "save_observations": {"request": "observation_recording_request"},
    "match_and_triangulate": {"observations": "camera_observations"},
    "filter_trajectories": {"science": "raw_recording_geometry"},
    "align_reference": {"science": "raw_recording_geometry", "filtered": "filtered_trajectories"},
    "reconstruction_input": {"aligned": "aligned_recording", "filtered": "filtered_trajectories"},
    "fit_model_dimensions": {"request": "reconstruction_input"},
    "reconstruct_skeletons": {"request": "reconstruction_input", "fits": "recording_model_fits"},
    "spatial_request": {"request": "observation_recording_request", "science": "raw_recording_geometry",
                        "filtered": "filtered_trajectories", "aligned": "aligned_recording"},
    "save_spatial": {"request": "spatial_recording_request", "saved_observations": "saved_observations"},
    "save_recording": {"request": "spatial_recording_request", "aligned": "aligned_recording",
                       "reconstructions": "reconstructed_models", "saved_spatial": "saved_spatial"},
    "export_scientific": {"saved": "saved_recording"},
    "export_tall_csv": {"saved": "saved_recording"},
    "annotate_camera": {"observations": "camera_observations"},
}


def build_recording_pipeline(*, sources: RecordingVideoSources, recording: RecordingInfo,
    config: PosthocMocapPipelineConfig, execution_provider: str = "cpu", annotate: bool = False,
    shutdown_flag=None, performance: PerformanceReport | None = None,
    observation_loader: Callable[[], ObservationCollection] | None = None,
) -> tuple[CompiledGraph, dict[str, Callable[[dict[str, object]], dict[str, object]]]]:
    """Build the same definition that execution consumes; callers may serialize it.

    An injected observation loader is the comparison seam, not another numerical
    implementation. First route supports fresh multicamera processing. Saved-stage
    resume, automatic board discovery and Blender launch require later adapters.
    """
    config = config.model_copy(deep=True)
    if execution_provider not in ("cpu", "cuda") or (config.detector_type == "mediapipe" and execution_provider != "cpu"):
        raise ValueError("Choose CPU/CUDA for RTMPose; the installed MediaPipe adapter supports CPU only")
    if config.start_stage != "observations" or config.export_to_blender:
        raise ValueError("Experimental recording graph requires fresh observations and Blender export disabled")
    if config.charuco_tracking_enabled and config.board_mode != CharucoBoardMode.EXPLICIT:
        raise ValueError("Experimental recording graph requires an explicit board definition")
    if len(sources.camera_sources) < 2 or not config.calibration_toml_path:
        raise ValueError("Experimental recording graph requires multicamera calibration")
    if config.sensor_group is not None and config.sensor_group != sources.sensor_group:
        raise ValueError("Configured sensor group differs from resolved recording sources")
    if Path(recording.full_recording_path).resolve() != sources.recording_path.resolve():
        raise ValueError("Graph destination must own its source videos")
    calibration_path = Path(config.calibration_toml_path).resolve()
    if not calibration_path.is_relative_to(Path(recording.full_recording_path).resolve()):
        raise ValueError("Experimental graph requires a private calibration copy inside its recording")
    calibration_mtime = calibration_path.stat().st_mtime_ns / 1_000_000
    calibration = CalibrationResult.load_toml(calibration_path)
    if calibration_path.stat().st_mtime_ns / 1_000_000 != calibration_mtime:
        raise ValueError("Calibration changed while loading")
    shutdown_flag = shutdown_flag if shutdown_flag is not None else multiprocessing.Value("b", False)
    performance = performance if performance is not None else PerformanceReport()
    tracker_config = config.tracker_config.model_copy(deep=True)
    bundles = (build_standard_human_bundle(detector_type=config.detector_type, anchor_segment_name=config.anchor_segment_name),)
    if config.charuco_tracking_enabled:
        tracker_config.stages.append(DetectionStageConfig(name="charuco",
            keypoint_detectors=[CharucoDetectorConfig(board=config.charuco_board)]))
        bundles += (build_charuco_board_bundle(board=config.charuco_board),)
    model_name = config.rtmpose_model_name if config.detector_type == "rtmpose" else MEDIAPIPE_WHOLEBODY_DEFINITION.name
    tracker_source = f"keypoint_model:{model_name}"
    timing = RecordingGroupTiming(cameras={source.camera_id: source.camera_timing for source in sources.camera_sources},
                                  synchronized=sources.group_timing)
    videos = {source.camera_id: source.video_metadata for source in sources.camera_sources}
    nodes, edges, handlers = [], [], {}
    execution_id = str(uuid4())

    def check_cancelled():
        if shutdown_flag.value:
            raise CancelledError("Recording graph cancelled")

    def operation(name, kind, dependencies, function, resource="compute"):
        def port(port_name, contract_kind):
            return GraphPort(name=port_name, contract=DataContract(kind=contract_kind, data_granularity=DataGranularity.RECORDING))
        required = RECORDING_INPUT_CONTRACTS["annotate_camera" if name.startswith("annotate_camera_") else name]
        if set(required) != set(dependencies):
            raise ValueError(f"Operation input bindings differ from its contract: {name}")
        nodes.append(GraphNode(id=name, operation=name, execution_resource=resource,
            inputs=tuple(port(input_name, required[input_name]) for input_name in dependencies),
            outputs=(port("result", kind),)))
        edges.extend(GraphConnection(source=PortReference(node=parent, port="result"),
            target=PortReference(node=name, port=input_name), binding=InputBindingRule.SAME_KEY)
            for input_name, parent in dependencies.items())
        def invoke(inputs):
            check_cancelled()
            return {"result": function(inputs)}
        handlers[name] = invoke

    def load_and_track(_):
        if observation_loader is not None:
            return observation_loader()
        collection = ObservationCollection(sources=sources, execution_id="recording-graph")
        registry = WorkerRegistry(global_kill_flag=shutdown_flag, worker_mode=WorkerMode.THREAD)
        service = InferenceService(worker_registry=registry)
        service.start()
        try:
            adapter = SkellyTrackerAdapter(inference_service=service, tracker_config=tracker_config,
                performance_report=performance, execution_provider=execution_provider,
                mediapipe_disable_gpu=True if config.detector_type == "mediapipe" else None)
            with closing(adapter.track_recording(sources=sources, execution_id="recording-graph", shutdown_flag=shutdown_flag)) as events:
                for event in events:
                    collection.accept(event)
        finally:
            service.close()
            registry.remove_dead()
        return collection

    operation("load_and_track", "camera_observations", {}, load_and_track)

    def triangulate(inputs):
        collection = inputs["observations"]
        return triangulate_completed_observations(collection=collection,
            calibration_cameras=tuple(calibration.cameras), matching_config=config.camera_matching,
            triangulation_config=config.triangulation_config, cancelled=lambda: bool(shutdown_flag.value))

    operation("match_and_triangulate", "raw_recording_geometry", {"observations": "load_and_track"}, triangulate)
    operation("filter_trajectories", "filtered_trajectories", {"science": "match_and_triangulate"}, lambda inputs:
        prepare_recording_points(points=inputs["science"].triangulation.reconstruction.points_3d,
            timestamps_s=np.asarray(timing.synchronized.timestamps_s), config=config.filter_config))

    def align(inputs):
        science, filtered = inputs["science"], inputs["filtered"]
        return align_mocap_recording(request=MocapAlignmentRequest(filtered_points=filtered.points,
            measured_support=filtered.report.gap_filling.measured_support(filtered.points),
            triangulation=science.triangulation, camera_geometry=science.camera_geometry, bundle=bundles[0],
            definition=AlignmentDefinition.from_default_human(skeleton=bundles[0].skeleton),
            timestamps_seconds=np.asarray(timing.synchronized.timestamps_s),
            preserve_reference_frame=config.body_alignment.preserve_reference_frame(calibration_aligned=calibration.aligned),
            config=config.body_alignment))

    operation("align_reference", "aligned_recording", {"science": "match_and_triangulate", "filtered": "filter_trajectories"}, align)
    operation("reconstruction_input", "reconstruction_input", {"aligned": "align_reference", "filtered": "filter_trajectories"}, lambda inputs:
        RecordingReconstructionInput(bundles=bundles,
            keypoint_names=inputs["aligned"].triangulation.keypoint_names, keypoints_3d=inputs["aligned"].filtered_points,
            measured_support=inputs["filtered"].report.gap_filling.measured_support(inputs["aligned"].filtered_points),
            compute_center_of_mass=True, timing=PosthocTimingReport()))
    operation("fit_model_dimensions", "recording_model_fits", {"request": "reconstruction_input"},
              lambda inputs: fit_skeletons_for_recording(inputs["request"]))
    operation("reconstruct_skeletons", "reconstructed_models", {"request": "reconstruction_input", "fits": "fit_model_dimensions"},
              lambda inputs: reconstruct_skeletons_with_fits(request=inputs["request"], fits=inputs["fits"]))

    def observation_request(inputs):
        collection = inputs["observations"]
        collection.require_complete()
        definition = config.model_dump(mode="json")
        definition["execution"] = {"requested_provider": execution_provider, "timestamp_policy": "relative_recording_group_milliseconds"}
        return ObservationRecordingRequest(recording=recording,
            group=ObservationGroup(name=sources.sensor_group, frames=collection.frames, videos=videos),
            tracker=TrackerRecordingDefinition(name=tracker_source,
                point_names=tuple(dict.fromkeys(name for frame in collection.frames for observation in frame.values()
                                                for name in observation.to_keypoints().names)), configuration=definition),
            detector=DetectorRecordingDefinition(name="object_detector:yolox-m",
                box_names=tuple(dict.fromkeys(stage.name for frame in collection.frames for observation in frame.values()
                                              for stage in observation.stages.values())), configuration=definition)
                if config.detector_type == "rtmpose" else None,
            models=tuple(RecordedModel.from_bundle(bundle) for bundle in bundles),
            camera_geometry=(), spatial_series=(), filtering=None, reprojection=None, reconstructions=(),
            base_run_id=config.base_run_id, resolved_timing=timing,
            provenance_context=ProvenanceContext.create(), provenance_defaults=PosthocMocapPipelineConfig().model_dump(mode="json"))

    operation("observation_request", "observation_recording_request", {"observations": "load_and_track"}, observation_request)
    operation("save_observations", "saved_observations", {"request": "observation_request"},
              lambda inputs: publish_posthoc_observations(inputs["request"]), resource="recording_io")

    def spatial_request(inputs):
        request, science, filtered, aligned = (inputs[name] for name in ("request", "science", "filtered", "aligned"))
        reference = SpatialReference.for_camera_count(len(videos)).model_copy(update={
            "alignment": ReferenceAlignmentDescriptor.from_result(result=aligned.alignment),
            "additional_transform": config.body_alignment.additional_transform})
        return replace(request, reuse_observations=True,
            camera_assignment=camera_assignment_metadata(science.matching_result, science.camera_geometry),
            camera_geometry=tuple(aligned.camera_geometry[source] for source in videos),
            spatial_series=tuple(SpatialPointSeries(definition=PointSeriesDefinition(kind=kind,
                sensor_group=sources.sensor_group, source=tracker_source, names=aligned.triangulation.keypoint_names,
                reference=reference), values=values) for kind, values in (
                    (ChannelKind.RAW_KEYPOINTS_3D, aligned.triangulation.reconstruction.points_3d),
                    (ChannelKind.KEYPOINTS_3D, aligned.filtered_points))),
            filtering=filtered.report,
            reprojection=NamedReprojectionDiagnostics(source_ids=aligned.triangulation.sources,
                point_names=aligned.triangulation.diagnostic_point_names, values=aligned.triangulation.reconstruction.diagnostics),
        )

    operation("spatial_request", "spatial_recording_request", {"request": "observation_request",
        "science": "match_and_triangulate", "filtered": "filter_trajectories", "aligned": "align_reference"}, spatial_request)
    operation("save_spatial", "saved_spatial", {"request": "spatial_request", "saved_observations": "save_observations"},
              lambda inputs: publish_posthoc_observations(inputs["request"]), resource="recording_io")

    def save_recording(inputs):
        request, aligned, reconstructions = (inputs[name] for name in ("request", "aligned", "reconstructions"))
        publication = replace(request,
            reconstructions=tuple(ReconstructionRecording(sensor_group=sources.sensor_group, reference=request.spatial_series[0].definition.reference,
                definition=ReconstructionSourceDefinition.from_bundle(bundle, tracker_source=tracker_source, point_kind=ChannelKind.KEYPOINTS_3D),
                result=reconstructions[bundle.model_id]) for bundle in bundles),
            calibration_update=CalibrationUpdateRequest(path=calibration_path, expected_mtime_ms=calibration_mtime,
                transformations=aligned.transformations, recording_id=recording.recording_name) if aligned.transformations else None)
        check_cancelled()
        return publish_posthoc_observations(publication)

    operation("save_recording", "saved_recording", {"request": "spatial_request", "saved_spatial": "save_spatial",
        "aligned": "align_reference", "reconstructions": "reconstruct_skeletons"}, save_recording, resource="recording_io")

    if config.scientific_exports.formats:
        def export_science(_):
            from freemocap.core.recording.exports.requests import ScientificExportRequest
            from freemocap.core.recording.exports.wide_csv import export_scientific
            return export_scientific(structure=RecordingStructure(base_directory=Path(recording.recording_directory), recording_name=recording.recording_name),
                request=ScientificExportRequest(**config.scientific_exports.model_dump(), run_id=config.base_run_id),
                cancelled=lambda: bool(shutdown_flag.value))
        operation("export_scientific", "export_manifest", {"saved": "save_recording"}, export_science)
    if config.export_tall_csv:
        def export_tall(_):
            from freemocap.core.recording.exports.tall_csv import TallCsvRequest, export_tall_csv
            return export_tall_csv(structure=RecordingStructure(base_directory=Path(recording.recording_directory), recording_name=recording.recording_name),
                request=TallCsvRequest(run_id=config.base_run_id), cancelled=lambda: bool(shutdown_flag.value))
        operation("export_tall_csv", "tall_csv_manifest", {"saved": "save_recording"}, export_tall)

    if annotate:
        for index, source in enumerate(sources.camera_sources):
            def annotate_camera(inputs, source=source):
                collection = inputs["observations"]
                if not any(outcome.camera_id == source.camera_id and outcome.outcome == ProducerOutcome.SUCCEEDED for outcome in collection.outcomes):
                    raise ValueError(f"Camera did not complete: {source.camera_id}")
                annotator = build_observation_annotator(tracker_config)
                reader = cv2.VideoCapture(str(source.video_metadata.file_path))
                output = None
                try:
                    output = AnnotationVideoOutput(AnnotationOutputRequest(recording_path=Path(recording.full_recording_path),
                        pipeline_id=execution_id, video=source.video_metadata, input_mode=AnnotationInput.RAW,
                        performance=performance, camera_id=source.camera_id))
                    for frame in collection.frames:
                        check_cancelled()
                        ok, image = reader.read()
                        if not ok:
                            raise ValueError("Annotation video ended before observations")
                        output.write_frame(image=image, observation=frame[source.camera_id], annotator=annotator)
                    output.publish()
                    return output.destination
                finally:
                    reader.release()
                    if output is not None:
                        output.close()
            operation(f"annotate_camera_{index}", "annotated_video", {"observations": "load_and_track"}, annotate_camera, resource="annotation")
    return compile_graph(GraphDefinition(nodes=tuple(nodes), edges=tuple(edges))), handlers


def run_recording_pipeline(**kwargs) -> RecordingExecutionResult:
    graph, handlers = build_recording_pipeline(**kwargs)
    flag = kwargs.get("shutdown_flag")
    return execute_recording_graph(graph=graph, handlers=handlers, cancelled=lambda: bool(flag.value) if flag is not None else False)
