from itertools import islice

import pytest

from freemocap.tools.hardware_validation.matrix_plan import MatrixPlan, camera_subsets


def test_every_camera_subset_and_directed_transition_is_present():
    plan = MatrixPlan(('C', 'A', 'B'), setting_axes={'exposure': [-7]})
    cases = list(plan.transition_cases())
    assert len(camera_subsets(plan.camera_ids)) == 8
    assert len(cases) == plan.counts()['camera_transition'] == 768
    assert len({case.case_id for case in cases}) == len(cases)
    assert any(case.initial_cameras == ('A', 'B') and case.requested_cameras == ('A',)
               and case.initial_state == 'recording' for case in cases)
    assert any(case.initial_cameras == ('A',) and case.requested_cameras == ('A', 'B') for case in cases)
    assert any(not case.initial_cameras and case.initial_state == 'recording' for case in cases)


def test_settings_cartesian_product_targets_individuals_and_subsets():
    plan = MatrixPlan(('A', 'B', 'C'), setting_axes={'exposure': [-7, -5], 'rotation': [-1, 0]})
    cases = list(plan.settings_cases())
    assert len(cases) == plan.counts()['camera_settings'] == 456
    selected = [case for case in cases if case.capture_backend == 'python'
                and case.initial_cameras == ('A', 'B', 'C') and case.requested_cameras == ('B',)
                and case.initial_state == 'recording']
    assert {(case.camera_settings['exposure'], case.camera_settings['rotation']) for case in selected} == {
        (-7, -1), (-7, 0), (-5, -1), (-5, 0)}


def test_case_identifiers_are_stable_and_full_settings_plan_is_lazy():
    first = list(islice(MatrixPlan(('A', 'B', 'C')).settings_cases(), 2))
    second = list(islice(MatrixPlan(('C', 'B', 'A')).settings_cases(), 2))
    assert [case.case_id for case in first] == [case.case_id for case in second]
    with pytest.raises(ValueError, match='distinct'):
        camera_subsets(('A', 'A'))
