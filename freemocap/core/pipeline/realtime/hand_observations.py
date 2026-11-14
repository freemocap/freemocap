"""Associate camera-local hand tracks using bound cameras and their reprojection error."""
from collections import Counter
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellytracker.core.data_primitives.tracked_hand import TrackedHand
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.reconstruction.coordinate_conventions import CALIBRATION_TO_RECONSTRUCTION
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.triangulator import Triangulator

_PAIR_CONFIG = TriangulationConfig(use_outlier_rejection=False)


@dataclass
class HandObservation:
    track_id: int
    handedness: str
    views: dict[str, TrackedHand]
    xyz: np.ndarray | None


class HandAssociation:
    def __init__(self):
        self.next_id = 0
        self.history = {}
        self.frame = 0
        self.binding = None
        self.pairs = {}

    def _pair_scores(self, camera_a, camera_b, hands_a, hands_b):
        pair = (camera_a, camera_b)
        if pair not in self.pairs:
            self.pairs[pair] = Triangulator(cameras=[self.binding.by_live_id[c] for c in pair])
        triangulator = self.pairs[pair]
        # One batched DLT call scores every candidate pair of hands in these
        # two views. The triangulator owns distortion, projection and units.
        left = np.stack([hand.keypoints.xy for hand in hands_a])
        right = np.stack([hand.keypoints.xy for hand in hands_b])
        pixels = np.stack((np.repeat(left, len(right), axis=0), np.tile(right, (len(left), 1, 1))))
        result = triangulator.triangulate(data2d=pixels, config=_PAIR_CONFIG)
        valid = np.isfinite(result.reprojection_error).all(axis=0)
        for camera in triangulator.cameras:
            depth = result.points_3d @ camera.extrinsics.rotation_matrix[2] + camera.extrinsics.translation[2]
            valid &= depth > 0
        usable = valid.sum(axis=1) > valid.shape[1] // 2
        scores = np.full(len(valid), np.inf)
        errors = np.where(valid[None, usable, :], result.reprojection_error[:, usable, :], np.nan)
        scores[usable] = np.nanmedian(errors, axis=(0, 2))
        return scores.reshape(len(left), len(right))

    def update(self, observations, calibration, config, max_error_px, triangulate):
        self.frame += 1
        binding = calibration.binding if calibration.is_applicable() else None
        if binding is not self.binding:
            self.pairs.clear()
            self.binding = binding
        views = {cam: obs.stages["hands"].hands for cam, obs in observations.items() if "hands" in obs.stages}
        hands = {(cam, hand.track_id): hand for cam, items in views.items() for hand in items}
        groups = [{key} for key in hands]
        edges = {}
        if binding is not None:
            cameras = sorted(cam for cam in views if views[cam] and cam in binding.by_live_id and binding.by_live_id[cam] is not None)
            for ca, cb in combinations(cameras, 2):
                scores = self._pair_scores(ca, cb, views[ca], views[cb])
                for i, j in zip(*np.where(scores <= max_error_px)):
                    score = scores[i, j]
                    # Require a distinct best match in both views, including when
                    # two hands carry the same handedness or exchange positions.
                    margin = max(1., score * .25)
                    if ((np.delete(scores[i], j) <= score + margin).any()
                            or (np.delete(scores[:, j], i) <= score + margin).any()):
                        continue
                    a, b = (ca, views[ca][i].track_id), (cb, views[cb][j].track_id)
                    edges[frozenset((a, b))] = score
        for edge in sorted(edges, key=edges.get):
            a, b = edge
            ga = next(group for group in groups if a in group)
            gb = next(group for group in groups if b in group)
            if ga is not gb and all(frozenset((x, y)) in edges for x in ga for y in gb):
                ga.update(gb)
                groups.remove(gb)

        self.history = {key: entry for key, entry in self.history.items() if self.frame - entry[1] <= 10}
        used = set()
        output = []
        for group in sorted(groups, key=lambda g: (-len(g), sorted(g))):
            prior = Counter(self.history[key][0] for key in sorted(group) if key in self.history)
            track_id = next((track for track, _ in prior.most_common() if track not in used), None)
            if track_id is None:
                track_id = self.next_id
                self.next_id += 1
            used.add(track_id)
            for key in group:
                self.history[key] = (track_id, self.frame)
            selected = {cam: hands[(cam, local)] for cam, local in sorted(group)}
            side = Counter(h.handedness for h in selected.values()).most_common(1)[0][0]
            xyz = None
            if triangulate and len(group) >= config.minimum_cameras_for_triangulation:
                aligned = {cam: Observation(observations[cam].frame_number, observations[cam].image_size,
                           {"hand": StageObservation("hand", keypoints=h.keypoints)}) for cam, h in selected.items()}
                result = calibration.try_angulate(frame_number=next(iter(aligned.values())).frame_number,
                    frame_observations_by_camera=aligned, max_reprojection_error_px=max_error_px,
                    triangulation_config=config)
                if result is not None:
                    names = next(iter(selected.values())).keypoints.names
                    xyz = CALIBRATION_TO_RECONSTRUCTION.convert_point(
                        point=Point.from_prevalidated_array(array=result.points.aligned(names))).array
            output.append(HandObservation(track_id, side, selected, xyz))
        return tuple(output)
