"""Spatial channels retain units, coordinates and bounded batch sizes."""

from freemocap.core.recording.channel_series import SeriesSampling

import numpy as np
import pyarrow as pa
import pytest

from freemocap.core.recording.sample_conventions import SampleUnit
from freemocap.core.recording.spatial_point_series import (
    PointSeriesDefinition,
    SpatialPointSeries,
    SpatialReference,
    SpatialReferenceName,
)


def test_planar_points_are_pixels_and_batches_are_bounded() -> None:
    series = SpatialPointSeries(
        definition=PointSeriesDefinition(
            sensor_group="mocap",
            source="tracker",
            names=("wrist",),
            reference=SpatialReference.for_camera_count(1),
        ),
        values=np.array([[[1.0, 2.0, 3.0]], [[np.nan, np.nan, np.nan]]]),
    )
    batches = list(
        series.batches(
            SeriesSampling(
                frame_numbers=(5, 6), timestamps_s=(0.2, 0.24), run_id=0, batch_size=2
            )
        )
    )
    assert all(batch.num_rows == 2 for batch in batches)
    rows = pa.Table.from_batches(batches).to_pylist()
    assert all(row["units"] == SampleUnit.PIXELS for row in rows)
    assert [row["value"] for row in rows] == [1.0, 2.0, 3.0, None, None, None]


def test_planar_reference_rejects_metric_units() -> None:
    with pytest.raises(ValueError, match="requires"):
        SpatialReference(
            name=SpatialReferenceName.CAMERA_PLANE, units=SampleUnit.MILLIMETERS
        )
