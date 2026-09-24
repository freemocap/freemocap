"""Known hierarchy answers plus one strictly read-only prepared-recording check."""

from pathlib import Path

import numpy as np
import pytest

from freemocap.tests.inspect_export_hierarchy import inspect, measure_hierarchy


def example():
    # Moving root and rotating parent; values are authored in millimeters.
    parents = {"tip": "arm", "arm": "root", "branch": "root", "root": None}
    root = np.array([[0., 0., 100.], [10., 20., 110.], [30., 40., 120.]])
    rotation = np.array([np.eye(3), [[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]],
                         [[-1., 0., 0.], [0., -1., 0.], [0., 0., 1.]]])
    arm_rotation = rotation @ np.array([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]])
    # The arm attachment moves 10 mm between samples; branch remains fixed.
    arm = root + np.array([[10., 0., 0.], [0., 20., 0.], [-30., 0., 0.]])
    positions = {"root": root, "arm": arm,
                 "branch": root + np.array([[0., 7., 0.], [-7., 0., 0.], [0., -7., 0.]]),
                 "tip": arm + np.array([[0., -5., 0.], [5., 0., 0.], [0., 5., 0.]])}
    rotations = {"root": rotation, "arm": arm_rotation, "branch": rotation, "tip": arm_rotation}
    offsets = {"arm": np.array([10., 0., 0.]), "tip": np.array([0., 0., 5.]),
               "branch": np.array([0., 7., 0.])}
    return parents, positions, rotations, offsets


def test_fixed_offsets_measure_known_error_and_dynamic_offsets_recover_positions():
    args = example()
    before = {name: value.copy() for name, value in args[1].items()}
    result = measure_hierarchy(*args)
    for edge in result.values():
        assert edge["exact_fk_error_mm"]["max"] == pytest.approx(0.)
        assert edge["rotation_matrix_error"]["max"] == pytest.approx(0.)
    assert result["arm"]["mean_offset_mm"] == [20., 0., 0.]
    for name in ("arm", "tip"):
        assert result[name]["mean_offset_fk_error_mm"]["rms"] == pytest.approx(np.sqrt(200. / 3.))
        assert result[name]["fitted_rest_fk_error_mm"]["rms"] == pytest.approx(np.sqrt(500. / 3.))
    assert result["tip"]["offset_variation_mm"]["max"] == pytest.approx(0.)
    assert result["branch"]["fitted_rest_fk_error_mm"]["max"] == pytest.approx(0.)
    for name, value in before.items():
        np.testing.assert_array_equal(args[1][name], value)


def test_missing_ancestor_is_not_fabricated_even_when_child_pair_is_observed():
    args = example()
    args[1]["root"][1] = np.nan
    result = measure_hierarchy(*args)
    assert result["tip"]["valid_pair_frames"] == 3
    assert result["tip"]["exact_fk_error_mm"]["count"] == 2
    assert result["tip"]["mean_offset_fk_error_mm"]["count"] == 2


def test_entirely_missing_branch_reports_no_evidence_not_zero_error():
    args = example()
    args[2]["arm"] = np.full((3, 3, 3), np.nan)
    result = measure_hierarchy(*args)
    assert result["arm"]["mean_offset_mm"] is None
    assert result["tip"]["exact_fk_error_mm"] == {"count": 0, "rms": None, "p95": None, "max": None}


@pytest.mark.parametrize("parent", ["tip", "absent"])
def test_invalid_hierarchy_fails(parent):
    args = example()
    args[0]["root"] = parent
    with pytest.raises(ValueError, match="cycle or unknown parent"):
        measure_hierarchy(*args)


@pytest.mark.e2e
def test_prepared_export_hierarchy_without_processing():
    path = (Path.home() / "freemocap_data/testing/prepared/freemocap_test_data/current/recordings"
            / "freemocap_test_data/freemocap_test_data_data.parquet")
    if not path.is_file():
        pytest.skip("Requires existing prepared test Parquet; this check never prepares data")
    report = inspect(path)
    assert report["frames"] == 222
    assert report["fitted_model_scale_mm"] > 0
    evidence = [edge for edge in report["edges"].values() if edge["exact_fk_error_mm"]["count"]]
    assert evidence, "No complete observed hierarchy paths"
    for edge in evidence:
        assert edge["exact_fk_error_mm"]["max"] < 1e-8
        assert edge["rotation_matrix_error"]["max"] < 1e-10
    # Deliberately no accuracy threshold for the approximate rig: this test must
    # allow reconstruction to improve rather than freezing today's errors.
