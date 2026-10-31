"""Compose image admission, spatial rejection and dense filtering in Core.

The aggregator owns this pipeline, so both inference paths use identical stages.
Metadata dictionaries identify streams, never point values.
"""
from copy import copy
import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues
from freemocap.core.pipeline.realtime.realtime_keypoint_filter import RealtimeKeypointFilter, FilteredKeypoints
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
from freemocap.core.tasks.mocap.realtime_filtering.realtime_point_gate import RealtimePointGate


def capture_timestamp(frame: np.recarray) -> float:
    stamps = frame.frame_metadata.timestamps
    before = int(stamps.pre_frame_grab_ns[0])
    after = int(stamps.post_frame_grab_ns[0])
    if before <= 0 or after < before:
        raise ValueError('Capture timestamps must be positive and ordered')
    return (before + (after - before) / 2) / 1e9


class TemporalPipeline:
    def __init__(self, config: RealtimeFilterConfig):
        self.config = config
        self.reset()

    def reset(self):
        self._metric_space = None
        self.image_filters = {}
        settings = self.config.spatial_smoothing
        self.spatial_filter = RealtimeKeypointFilter(min_cutoff=settings.min_cutoff, beta=settings.beta,
            d_cutoff=settings.d_cutoff, smoothing_enabled=settings.enabled,
            gap_duration_s=self.config.gap_duration_s, prediction_duration_s=self.config.prediction_duration_s,
            velocity_half_life_s=self.config.velocity_half_life_s)
        self.motion_gate = RealtimePointGate(max_velocity_mm_per_s=self.config.max_velocity_mm_per_s,
            reacquisition_timeout_s=self.config.reacquisition_timeout_s)

    def configure(self, config: RealtimeFilterConfig):
        previous = self.config
        self.config = config
        if previous.spatial_smoothing.enabled != config.spatial_smoothing.enabled:
            self.spatial_filter.reset()
        if previous.image_smoothing.enabled != config.image_smoothing.enabled:
            self.image_filters.clear()
        if previous.velocity_gate_enabled != config.velocity_gate_enabled:
            self.motion_gate.reset()
        self.spatial_filter.min_cutoff = config.spatial_smoothing.min_cutoff
        self.spatial_filter.beta = config.spatial_smoothing.beta
        self.spatial_filter.d_cutoff = config.spatial_smoothing.d_cutoff
        self.spatial_filter.smoothing_enabled = config.spatial_smoothing.enabled
        self.spatial_filter.gap_duration_s = config.gap_duration_s
        self.spatial_filter.prediction_duration_s = config.prediction_duration_s
        self.spatial_filter.velocity_half_life_s = config.velocity_half_life_s
        self.motion_gate.configure(max_velocity_mm_per_s=config.max_velocity_mm_per_s,
            reacquisition_timeout_s=config.reacquisition_timeout_s)
        for image_filter in self.image_filters.values():
            image_filter.min_cutoff = config.image_smoothing.min_cutoff
            image_filter.beta = config.image_smoothing.beta
            image_filter.d_cutoff = config.image_smoothing.d_cutoff

    def image_observation(self, *, camera_id: str, observation, timestamp_s: float, confidence_threshold: float):
        body = observation.stages.get('body') if observation is not None else None
        if body is None or body.keypoints is None:
            image_filter = self.image_filters.get(camera_id)
            if image_filter is not None:
                image_filter.filter(t=timestamp_s,
                    raw_keypoints=ChannelValues.empty(component_names=image_filter.component_names))
            return observation
        original = body.keypoints
        # Copy only the numerical channel we change; preserve raw detector results.
        keypoints = copy(original)
        keypoints.xyz = original.xyz.copy()
        present = np.isfinite(original.xy).all(axis=-1) & np.isfinite(original.visibility) & (original.visibility >= confidence_threshold)
        keypoints.xy[~present] = np.nan
        settings = self.config.image_smoothing
        if settings.enabled:
            image_filter = self.image_filters.get(camera_id)
            if image_filter is None:
                image_filter = RealtimeKeypointFilter(dims=original.xy.shape[-1], min_cutoff=settings.min_cutoff,
                    beta=settings.beta, d_cutoff=settings.d_cutoff, gap_duration_s=0.0)
                self.image_filters[camera_id] = image_filter
            positions = image_filter.filter(t=timestamp_s,
                raw_keypoints=ChannelValues(original.names, original.xy, present, component_names=('x', 'y'))).positions
            np.copyto(keypoints.xy, positions.aligned(original.names))
        result = copy(observation)
        result.stages = observation.stages.copy()
        result.stages['body'] = copy(body)
        result.stages['body'].keypoints = keypoints
        return result

    def process(self, *, timestamp_s: float, points: ChannelValues, metric_space: bool = True) -> FilteredKeypoints:
        if self._metric_space is not None and self._metric_space != metric_space:
            self.reset()
        self._metric_space = metric_space
        # Single-camera positions are pixels; never apply millimeter parameters.
        self.spatial_filter.smoothing_enabled = self.config.spatial_smoothing.enabled and metric_space
        accepted = points
        if self.config.velocity_gate_enabled and metric_space:
            gate = self.motion_gate.gate(t=timestamp_s, points=points)
            accepted = gate.positions.with_values(gate.positions.data_values,
                gate.positions.entry_present & ~gate.held_mask)
        return self.spatial_filter.filter(t=timestamp_s, raw_keypoints=accepted)
