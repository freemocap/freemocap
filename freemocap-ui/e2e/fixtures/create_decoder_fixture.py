"""Generate an H.264 B-frame fixture and its sequential PyAV pixel reference."""

import json
from pathlib import Path

import av
import numpy as np


def main() -> None:
    folder = Path(__file__).parent
    path = folder / "numbered-bframes.mp4"
    with av.open(str(path), mode="w") as output:
        stream = output.add_stream("libx264", rate=30)
        stream.width = 640
        stream.height = 480
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "12", "x264-params": "bframes=2:b-adapt=0:keyint=12:scenecut=0"}
        for ordinal in range(48):
            pixels = np.zeros((480, 640, 3), dtype=np.uint8)
            for bit in range(8):
                pixels[:, bit * 80:(bit + 1) * 80] = 220 if ordinal & (1 << bit) else 30
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    references: list[list[int]] = []
    b_frames = 0
    with av.open(str(path)) as source:
        for frame in source.decode(video=0):
            b_frames += int(frame.pict_type == 3)
            pixels = frame.to_ndarray(format="rgb24")
            references.append([int(pixels[240, bit * 80 + 40, 0]) for bit in range(8)])
    if not b_frames or len(references) != 48:
        raise RuntimeError("Fixture requires 48 frames including B-frames")
    (folder / "numbered-bframes.json").write_text(json.dumps(references), encoding="utf-8")
    print(f"Generated 48 reference frames, including {b_frames} B-frames")


if __name__ == "__main__":
    main()
