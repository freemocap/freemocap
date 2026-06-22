import numpy as np
from freemocap.core.kinematics.online.streaming_kinematics import StreamingKinematics


def _masses():
    return {"a": 1.0, "b": 1.0}


def _coms_at(x_offset):
    # two masses straddling the x-offset, CoM height 1000 mm
    return {
        "a": np.array([x_offset + 1.0, 0.0, 1000.0]),
        "b": np.array([x_offset - 1.0, 0.0, 1000.0]),
    }, np.array([x_offset, 0.0, 1000.0])


def test_first_frame_has_ellipsoid_but_no_derivatives():
    sk = StreamingKinematics()
    coms, com = _coms_at(0.0)
    state = sk.update(t=0.0, whole_body_com=com, segment_coms=coms, segment_masses=_masses())
    assert state.center_of_mass.x == 0.0
    assert state.ellipsoid_semi_axes is not None      # ellipsoid needs no history
    assert state.com_velocity is None                  # no velocity yet
    assert state.xcom is None                          # needs velocity
    assert state.cmp is None                           # needs acceleration


def test_velocity_and_xcom_after_two_frames():
    sk = StreamingKinematics()
    c0, com0 = _coms_at(0.0)
    sk.update(t=0.0, whole_body_com=com0, segment_coms=c0, segment_masses=_masses())
    c1, com1 = _coms_at(10.0)  # moved +10 mm in x over 1 s
    state = sk.update(t=1.0, whole_body_com=com1, segment_coms=c1, segment_masses=_masses())
    assert state.com_velocity is not None
    assert np.isclose(state.com_velocity.x, 10.0)      # 10 mm / 1 s
    assert state.xcom is not None
    assert state.cmp is None                            # still need a 3rd frame
