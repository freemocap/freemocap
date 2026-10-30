"""Polars boundaries preserve declared axes, nulls and timestamp reduction."""
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest

from freemocap.core.recording.exports.notebook import TABLE
from freemocap.core.tasks.mocap.mocap_helpers.recording_framerate import (
    _median_framerate_from_csv, get_recording_framerate,
)


def notebook_scope(tmp_path, *, changes=None):
    data = dict(run_id=[3, 3, 3, 3, 99, 3], sensor_group=['camera'] * 6,
        source=['tracker'] * 6, channel=['OVERLAY_2D'] * 6,
        reference_frame=[None, None, None, None, None, 'other-camera'],
        frame_number=[42, 10, 10, 10, 10, 10], timestamp_s=[1.5, .5, .5, .5, .5, .5],
        name=['body.b', 'body.a', 'body.a', 'body.a', 'body.a', 'body.a'],
        component=['y', 'x', 'y', 'visibility', 'x', 'x'],
        units=['px', 'px', 'px', '1', 'px', 'px'],
        value=[8., 4., None, .9, 999., 999.])
    if changes:
        data.update(changes)
    path = tmp_path / 'channel.parquet'
    pl.DataFrame(data).write_parquet(path)
    channel = dict(names=['body.b', 'body.a'], components=['y', 'confidence', 'x'],
                   units=['px', '1', 'px'])
    context = dict(sensor_group='camera', source='tracker', channel='OVERLAY_2D', reference_frame=None)
    return dict(np=np, pl=pl, parquet_path=path, channel=channel, context=context, RUN_ID=3)


def test_notebook_tensor_order_sparse_presence_and_full_channel_selection(tmp_path):
    scope = notebook_scope(tmp_path)
    exec(TABLE, scope)
    expected = np.full((2, 2, 3), np.nan)
    expected[1, 0, 0] = 8.
    expected[0, 1, 1:] = [.9, 4.]
    np.testing.assert_array_equal(scope['values'], expected)
    np.testing.assert_array_equal(scope['frame_numbers'], [10, 42])
    np.testing.assert_array_equal(scope['times'].to_numpy(), [.5, 1.5])
    assert scope['present'].sum() == 4
    assert scope['present'][0, 1, 0]  # Recorded null remains distinct from absent.
    assert not scope['present'][0, 0, 0]
    assert isinstance(scope['table'], pl.DataFrame)
    plan = scope['channel_query'].explain()
    assert 'SELECTION' in plan and 'PROJECT' in plan


@pytest.mark.parametrize('changes,match', [
    ({'component': ['y', 'x', 'x', 'visibility', 'x', 'x']}, 'Duplicate sample'),
    ({'timestamp_s': [1.5, .5, .8, .5, .5, .5]}, 'Conflicting timestamps'),
    ({'timestamp_s': [1.5, .5, np.nextafter(.5, 1.), .5, .5, .5]}, 'Conflicting timestamps'),
    ({'timestamp_s': [1.5, .5, float('nan'), .5, .5, .5]}, 'Invalid sample'),
    ({'units': ['px', 'm', 'px', '1', 'px', 'px']}, 'units differ'),
])
def test_notebook_rejects_invalid_sample_data(tmp_path, changes, match):
    with pytest.raises(ValueError, match=match):
        exec(TABLE, notebook_scope(tmp_path, changes=changes))


def test_notebook_rejects_undeclared_names(tmp_path):
    with pytest.raises(pl.exceptions.InvalidOperationError, match='incomplete mapping'):
        exec(TABLE, notebook_scope(tmp_path, changes={'name': ['unknown'] + ['body.a'] * 5}))


@pytest.mark.parametrize('rates,expected', [
    (['30'] * 10 + ['', 'NaN', 'nan', 'NA', '0', '-1'], 30.),
    (['30'] * 9 + ['', 'NaN', '0'], None),
    (['15'] * 2 + ['30'] * 10, 30.),
])
def test_timestamp_csv_reduces_valid_samples_in_polars(tmp_path, rates, expected):
    path = tmp_path / 'timestamps.csv'
    path.write_text('unrelated,from_previous.framerate.hz\n' +
                    '\n'.join(f'unused,{value}' for value in rates), encoding='utf-8-sig')
    assert _median_framerate_from_csv(path) == expected


def test_timestamp_summary_avoids_csv_scan(tmp_path):
    folder = tmp_path / 'synchronized_videos' / 'timestamps'
    folder.mkdir(parents=True)
    (folder / 'recording_stats.json').write_text('{"framerate_stats": {"median": 60}}')
    with patch.object(pl, 'scan_csv', side_effect=AssertionError('Summary already supplies the rate')):
        assert get_recording_framerate(tmp_path) == 60.
