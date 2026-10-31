from freemocap.tools.hardware_validation.suite_plan import selected_cases


def test_quick_and_extended_suites_are_finite_and_cover_main_camera_actions():
    quick = selected_cases(('A', 'B', 'C'), 'quick')
    extended = selected_cases(('A', 'B', 'C'), 'extended')
    assert len(quick) == 15
    assert len(extended) == 32
    assert {case.case_name for case in quick} <= {case.case_name for case in extended}
    assert len({case.camera_ids for case in extended if case.case_name.startswith('record-')}) == 7
    assert {case.control_name for case in quick if case.control_name} == {
        'exposure', 'rotation', 'exposure-auto', 'exposure-recommend', 'resolution'}
