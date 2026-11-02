import cbor2
import numpy as np
import pytest

from freemocap_stream import encode_message


def test_envelope_comes_first_then_payload_fields_in_order():
    decoded = cbor2.loads(encode_message("robot_state", {"servos": {"pan": 90}, "mode": "live"}, timestamp=1.5, sequence=3))
    assert list(decoded) == ["kind", "version", "timestamp", "sequence", "servos", "mode"]
    assert decoded == {"kind": "robot_state", "version": 0, "timestamp": 1.5, "sequence": 3,
                       "servos": {"pan": 90}, "mode": "live"}


def test_top_level_none_fields_are_omitted_but_nested_none_is_kept():
    decoded = cbor2.loads(encode_message("robot_state", {"target": None, "camera": {"calibration": None}}))
    assert "target" not in decoded
    assert decoded["camera"] == {"calibration": None}


def test_byte_views_and_numpy_scalars_become_plain_values():
    decoded = cbor2.loads(encode_message("blob", {
        "view": memoryview(b"\x01\x02"), "buffer": bytearray(b"\x03"), "angle": np.float32(0.5), "count": np.int64(4),
    }))
    assert decoded["view"] == b"\x01\x02" and decoded["buffer"] == b"\x03"
    assert decoded["angle"] == 0.5 and decoded["count"] == 4


def test_timestamps_are_float64_so_clients_see_no_rounding():
    encoded = encode_message("tick", timestamp=1730000000.123456)
    assert cbor2.loads(encoded)["timestamp"] == 1730000000.123456


@pytest.mark.parametrize("payload", [{"kind": "other"}, {"sequence": 2}, {"version": 1}, {"timestamp": 0.0}])
def test_payload_cannot_replace_the_envelope(payload):
    with pytest.raises(ValueError, match="envelope"):
        encode_message("robot_state", payload)


def test_numerical_arrays_must_travel_as_channel_blocks():
    with pytest.raises(TypeError, match="channel blocks"):
        encode_message("points", {"xyz": np.zeros((2, 3))})
