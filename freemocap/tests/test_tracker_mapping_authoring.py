"""Cross-project mapping authoring belongs to Core and leaves authored data untouched."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import skellytracker
import yaml

from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from skellytracker.core.io.tracker_mapping import TrackerMapping
from freemocap.tools import generate_tracker_mapping_ratios as authoring


@pytest.fixture(params=['rtmpose', 'mediapipe'])
def mapping_path(request):
    return (Path(skellytracker.__file__).resolve().parent / 'core/detectors/keypoint_detectors'
            / request.param / 'body' / f'{request.param}_body_to_standard_human_mapping.yaml')


def test_authoring_solves_perturbed_offsets_using_the_actual_tracker_and_forge(mapping_path):
    skeleton = SkeletonDefinition.from_default_yaml()
    rest_pose = RestPose.from_default_yaml(skeleton=skeleton)
    targets = {name: rest_pose.landmark_positions[name].array for name in skeleton.landmarks}
    observed = authoring._synthetic_tpose_tracker_positions(rest_pose)
    entries = yaml.safe_load(mapping_path.read_text(encoding='utf-8'))
    for entry in entries.values():
        if isinstance(entry, dict) and entry.get('form') == 'anatomical_offset':
            for axis in entry['offset']:
                entry['offset'][axis] += 0.25
    unchanged = deepcopy(entries)
    corrected, notes = authoring._corrected_entries(entries, targets, observed)
    assert entries == unchanged and notes
    actual = TrackerMapping(entries=corrected).apply(tracker_positions=observed)
    for name, entry in corrected.items():
        if isinstance(entry, dict) and entry.get('form') == 'anatomical_offset' and name in targets:
            # The authoring CLI reports errors above 2 mm. Six-decimal ratio
            # rounding should reproduce the rest pose well inside that bound.
            assert np.linalg.norm(actual[name] - targets[name]) < 0.01
        else:
            assert entry == entries[name]


def test_report_command_reads_installed_mapping_without_rewriting_it(mapping_path, capsys):
    before = mapping_path.read_bytes()
    result = authoring.main([str(mapping_path)])
    report = capsys.readouterr().out
    assert result == 0
    assert mapping_path.name in report and 'corrected ratios' in report
    assert mapping_path.read_bytes() == before


def test_missing_arguments_explain_module_command(capsys):
    assert authoring.main([]) == 2
    assert 'python -m freemocap.tools.generate_tracker_mapping_ratios' in capsys.readouterr().out
