import numpy as np
import pytest

from freemocap_stream import PayloadImage, encode_image_payload

# SkellyCam declares the layout as numpy structs with align=True; reading the bytes
# back through these dtypes checks the struct formats against numpy's own padding rules.
HEADER = np.dtype([("message_type", "<u1"), ("frame_number", "<i8"), ("number_of_cameras", "<i4")], align=True)
IMAGE = np.dtype([("message_type", "<u1"), ("frame_number", "<i8"), ("camera_id", "S16"), ("camera_index", "<i4"),
                  ("image_width", "<i4"), ("image_height", "<i4"), ("color_channels", "<i4"),
                  ("jpeg_string_length", "<i4")], align=True)


def read(payload: bytes):
    header = np.frombuffer(payload, HEADER, count=1)[0]
    offset, images = HEADER.itemsize, []
    for _ in range(header["number_of_cameras"]):
        image = np.frombuffer(payload, IMAGE, count=1, offset=offset)[0]
        offset += IMAGE.itemsize
        images.append((image, payload[offset:offset + image["jpeg_string_length"]]))
        offset += image["jpeg_string_length"]
    footer = np.frombuffer(payload, HEADER, count=1, offset=offset)[0]
    assert offset + HEADER.itemsize == len(payload)
    return header, images, footer


def test_payload_matches_skellycams_aligned_layout():
    jpeg_a, jpeg_b = b"\xff\xd8 first \xff\xd9", np.frombuffer(b"\xff\xd8 second \xff\xd9", dtype=np.uint8)
    payload = encode_image_payload(41, [
        PayloadImage("oak", 0, 640, 480, jpeg_a),
        PayloadImage("zed-left", 3, 1280, 720, jpeg_b),
    ])
    header, images, footer = read(payload)
    assert (HEADER.itemsize, IMAGE.itemsize) == (24, 56)
    assert (header["message_type"], header["frame_number"], header["number_of_cameras"]) == (0, 41, 2)
    assert (footer["message_type"], footer["frame_number"], footer["number_of_cameras"]) == (2, 41, 2)
    (first, first_jpeg), (second, second_jpeg) = images
    assert (first["message_type"], first["frame_number"], first["camera_id"], first["camera_index"]) == (1, 41, b"oak", 0)
    assert (first["image_width"], first["image_height"], first["color_channels"]) == (640, 480, 3)
    assert (second["camera_id"], second["camera_index"], second["image_width"], second["image_height"]) == (b"zed-left", 3, 1280, 720)
    assert first_jpeg == jpeg_a and second_jpeg == jpeg_b.tobytes()


def test_padding_bytes_are_zero_like_numpys_zeroed_structs():
    payload = encode_image_payload(7, [PayloadImage("a", 0, 1, 1, b"\xff")])
    assert payload[1:8] == bytes(7) and payload[20:24] == bytes(7)[:4]
    assert payload[24 + 1:24 + 8] == bytes(7) and payload[24 + 52:24 + 56] == bytes(4)


@pytest.mark.parametrize("camera_id", ["", "x" * 17, "cam\0era", "caméra"])
def test_camera_ids_fit_the_16_byte_ascii_slot(camera_id):
    with pytest.raises(ValueError, match="Camera ID"):
        PayloadImage(camera_id, 0, 1, 1, b"\xff")


def test_one_payload_holds_unique_cameras_from_one_frame():
    with pytest.raises(ValueError, match="at least one image"):
        encode_image_payload(1, [])
    with pytest.raises(ValueError, match="IDs"):
        encode_image_payload(1, [PayloadImage("a", 0, 1, 1, b"\xff"), PayloadImage("a", 1, 1, 1, b"\xff")])
    with pytest.raises(ValueError, match="indices"):
        encode_image_payload(1, [PayloadImage("a", 0, 1, 1, b"\xff"), PayloadImage("b", 0, 1, 1, b"\xff")])
    with pytest.raises(ValueError, match="no JPEG bytes"):
        PayloadImage("a", 0, 1, 1, b"")
