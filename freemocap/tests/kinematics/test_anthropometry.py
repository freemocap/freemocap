from freemocap.core.kinematics.inertial.anthropometry import (
    SegmentInertialParameters,
    DE_LEVA_FEMALE,
    DE_LEVA_MALE,
    DE_LEVA_MEAN,
    segment_inertial_parameters,
)

_PRIMARY_SEGMENTS = {
    "head", "trunk", "upper_arm", "forearm", "hand", "thigh", "shank", "foot",
}
_BILATERAL = ["upper_arm", "forearm", "hand", "thigh", "shank", "foot"]


def test_known_male_thigh_values():
    # de Leva 1996, Table 4 (male): thigh mass 14.16%, CM 40.95%, radii 32.9/32.9/14.9
    thigh = DE_LEVA_MALE["thigh"]
    assert thigh.mass_fraction == 0.1416
    assert thigh.com_fraction == 0.4095
    assert (thigh.k_sagittal, thigh.k_transverse, thigh.k_longitudinal) == (0.329, 0.329, 0.149)


def test_known_female_foot_values():
    # de Leva 1996, Table 4 (female): foot mass 1.29%, radii 29.9/27.9/13.9
    foot = DE_LEVA_FEMALE["foot"]
    assert foot.mass_fraction == 0.0129
    assert (foot.k_sagittal, foot.k_transverse, foot.k_longitudinal) == (0.299, 0.279, 0.139)


def test_tables_share_the_primary_segments():
    assert set(DE_LEVA_FEMALE) == _PRIMARY_SEGMENTS
    assert set(DE_LEVA_MALE) == _PRIMARY_SEGMENTS
    assert set(DE_LEVA_MEAN) == _PRIMARY_SEGMENTS


def test_mean_is_average_of_female_and_male():
    f = DE_LEVA_FEMALE["foot"]
    m = DE_LEVA_MALE["foot"]
    mean = DE_LEVA_MEAN["foot"]
    assert mean.k_longitudinal == (f.k_longitudinal + m.k_longitudinal) / 2  # (0.139+0.124)/2
    assert mean.mass_fraction == (f.mass_fraction + m.mass_fraction) / 2
    assert mean.com_fraction == (f.com_fraction + m.com_fraction) / 2


def test_default_accessor_returns_mean():
    assert segment_inertial_parameters() == DE_LEVA_MEAN
    assert segment_inertial_parameters("male") == DE_LEVA_MALE
    assert segment_inertial_parameters("female") == DE_LEVA_FEMALE


def test_body_mass_fractions_sum_to_one():
    # Strong transcription check: head + trunk + 2x each limb segment == whole body.
    for table in (DE_LEVA_FEMALE, DE_LEVA_MALE, DE_LEVA_MEAN):
        total = table["head"].mass_fraction + table["trunk"].mass_fraction
        total += 2.0 * sum(table[s].mass_fraction for s in _BILATERAL)
        assert abs(total - 1.0) < 1e-3


def test_all_parameters_positive_and_fractional():
    for table in (DE_LEVA_FEMALE, DE_LEVA_MALE, DE_LEVA_MEAN):
        for params in table.values():
            for value in (
                params.mass_fraction, params.com_fraction,
                params.k_sagittal, params.k_transverse, params.k_longitudinal,
            ):
                assert 0.0 < value < 1.0
