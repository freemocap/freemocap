import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from freemocap.core.pipeline.posthoc_pipelines.video_helper import VideoHelper, VideoMetadata
from freemocap.core.types.type_overloads import VideoIdString


def extract_camera_id(filename: str) -> str | None:
    """
    Extract camera ID from filename using regex.

    Handles patterns like:
    - camera1, camera2, cam1, cam2
    - With various delimiters: . _ - or no delimiter
    - Case insensitive

    Args:
        filename: The filename to extract camera ID from

    Returns:
        The camera ID as a string, or None if not found
    """
    # Pattern explanation:
    # (?:camera|cam) - non-capturing group matching either "camera" or "cam"
    # [._\-]? - optional delimiter (dot, underscore, or hyphen)
    # (\d+) - capture group for one or more digits (the camera ID)
    pattern = r'(?:camera|cam)[._\-]?(\d+)'

    match = re.search(pattern, filename.lower())
    if match:
        return match.group(1)
    return None




# Test the extraction function
def test_camera_id_extraction():
    test_cases: list[tuple[str, str | None]] = [
        # Your examples
        ("2025-11-10_19-05-16_GMT-5_mocap.camera1.mp4", "1"),
        ("2025-11-10_19-05-16_GMT-5_mocap.camera2.mp4", "2"),

        # Various delimiter formats
        ("video_cam1.mp4", "1"),
        ("video-cam2.mp4", "2"),
        ("video.cam3.mp4", "3"),
        ("videocam4.mp4", "4"),
        ("CAMERA1.mp4", "1"),
        ("Camera_2.mp4", "2"),

        # Multi-digit camera IDs
        ("camera10.mp4", "10"),
        ("cam123.mp4", "123"),

        # Edge cases
        ("no_camera_here.mp4", None),
        ("just_a_video.mp4", None),
    ]

    for filename, expected in test_cases:
        result = extract_camera_id(filename)
        status = "✓" if result == expected else "✗"
        print(f"{status} {filename:40} -> {result} (expected: {expected})")


if __name__ == "__main__":
    test_camera_id_extraction()
