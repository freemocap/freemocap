"""Bounded pose retention over existing Forge tensors, before connected placement."""
import numpy as np


class PoseContinuity:
    def __init__(self):
        self.previous_poses = None
        self.observed_times = None

    def apply(self, *, poses, observed_present: np.ndarray, timestamp_s: float, duration_s: float):
        if self.previous_poses is None or self.previous_poses.segment_names != poses.segment_names:
            self.previous_poses = poses.copy_owned(writable=True)
            self.observed_times = np.full(poses.segment_present.shape, np.nan)
        current = poses.segment_present
        observed = current & observed_present
        self.observed_times[observed] = timestamp_s
        for saved, values in zip(self.previous_poses.arrays(), poses.arrays(), strict=True):
            mask = observed if saved.ndim == observed.ndim else observed[..., None]
            np.copyto(saved, values, where=mask)
        retained = ~current & np.isfinite(self.observed_times) & (timestamp_s - self.observed_times <= duration_s + 1e-9) & (duration_s > 0)
        if retained.any():
            # Hydration output is local to this call; no published tensor is mutated.
            poses = poses.copy_owned(writable=True)
            for target, saved in zip(poses.arrays(), self.previous_poses.arrays(), strict=True):
                mask = retained if target.ndim == retained.ndim else retained[..., None]
                np.copyto(target, saved, where=mask)
        status = poses.segment_present.astype(np.uint8)
        status[current & ~observed] = 2
        status[retained] = 3
        return poses, status[0]
