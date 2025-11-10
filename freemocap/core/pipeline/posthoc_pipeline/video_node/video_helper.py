"""
Simplified VideoHelper with OpenCV best practices.
Includes smart frame reading and caching.
"""

from pathlib import Path
from collections import OrderedDict
import cv2
import numpy as np
from pydantic import BaseModel, Field, ConfigDict, model_validator


# Module level constants
DEFAULT_CACHE_SIZE_MB = 500
SEQUENTIAL_READ_THRESHOLD = 5  # If reading within 5 frames ahead, use sequential


class VideoMetadata(BaseModel):
    """Video metadata container"""
    width: int
    height: int
    fps: float
    frame_count: int
    fourcc: str
    duration_seconds: float
    start_frame: int = 0
    end_frame: int

    @model_validator(mode="before")
    def validate_frames(cls, values):
        start_frame = values.get("start_frame", 0)
        values["end_frame"] = values.get("end_frame", values.get("frame_count"))
        end_frame = values["end_frame"]
        frame_count = end_frame - start_frame if end_frame is not None else values.get("frame_count")
        if end_frame is not None:
            if not (0 <= start_frame < end_frame <= frame_count):
                raise ValueError(f"Invalid start_frame or end_frame values: start_frame={start_frame}, end_frame={end_frame}, frame_count={frame_count}")
            if not (end_frame - start_frame) == frame_count:
                raise ValueError(f"Subset frame count does not match frame_count: {end_frame - start_frame} != {frame_count}")

        return values


class FrameCache(BaseModel):
    """LRU cache for video frames with memory management"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    max_size_mb: int = DEFAULT_CACHE_SIZE_MB
    frame_cache: OrderedDict[int, np.ndarray] = Field(default_factory=OrderedDict)
    current_bytes: int = Field(default=0)

    @property
    def _max_bytes(self) -> int:
        return self.max_size_mb * 1024 * 1024

    def get(self, frame_number: int) -> np.ndarray | None:
        if frame_number not in self.frame_cache:
            return None
        # Move to end (most recently used)
        self.frame_cache.move_to_end(frame_number)
        return self.frame_cache[frame_number].copy()

    def put(self, frame_number: int, frame: np.ndarray) -> None:
        frame_bytes = frame.nbytes

        # If frame already exists, update it
        if frame_number in self.frame_cache:
            old_bytes = self.frame_cache[frame_number].nbytes
            self.current_bytes -= old_bytes
            self.frame_cache.move_to_end(frame_number)

        # Evict frames if necessary based on size only
        while self.frame_cache and self.current_bytes + frame_bytes > self._max_bytes:
            evicted_frame_num, evicted_frame = self.frame_cache.popitem(last=False)
            self.current_bytes -= evicted_frame.nbytes

        # Add new frame
        self.frame_cache[frame_number] = frame.copy()
        self.current_bytes += frame_bytes

    def clear(self) -> None:
        self.frame_cache.clear()
        self.current_bytes = 0


class VideoHelper(BaseModel):
    """Video helper with caching and optimized frame reading"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    video_path: Path
    video_reader: cv2.VideoCapture = Field(exclude=True)
    metadata: VideoMetadata
    cache: FrameCache = Field(default_factory=lambda: FrameCache())

    # Reading optimization state
    last_read_frame: int = Field(default=-1)
    sequential_threshold: int = Field(default=SEQUENTIAL_READ_THRESHOLD)
    @property
    def has_frames(self) -> bool:
        """Check if video has frames."""
        return self.metadata.frame_count > 0 and self.last_read_frame < self.metadata.frame_count - 1

    @classmethod
    def from_video_path(
        cls,
        video_path: Path,
        *,
        cache_size_mb: int = DEFAULT_CACHE_SIZE_MB
    ) -> "VideoHelper":
        """
        Create a VideoHelper instance.

        Args:
            video_path: Path to the video file
            cache_size_mb: Maximum cache size in megabytes
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Open video capture
        video_reader = cv2.VideoCapture(str(video_path))
        if not video_reader.isOpened():
            raise RuntimeError(f"Failed to open video file: {video_path}")

        # Extract metadata
        width = int(video_reader.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video_reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = video_reader.get(cv2.CAP_PROP_FPS)
        frame_count = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
        fourcc_code = int(video_reader.get(cv2.CAP_PROP_FOURCC))

        # Convert fourcc to string
        fourcc = "".join([chr((fourcc_code >> 8 * i) & 0xFF) for i in range(4)])

        # Calculate duration
        duration_seconds = frame_count / fps if fps > 0 else 0.0

        metadata = VideoMetadata(
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            fourcc=fourcc,
            duration_seconds=duration_seconds
        )

        # Create cache
        cache = FrameCache(max_size_mb=cache_size_mb)

        return cls(
            video_path=video_path,
            video_reader=video_reader,
            metadata=metadata,
            cache=cache
        )

    def read_next_frame(self) -> np.ndarray| None:
        """
        Read the next frame in sequence. If the last read frame is -1, reads frame 0. If the last read frame is the last frame, returns None.


        Returns:
            Frame as numpy array
        """
        next_frame_number = self.last_read_frame + 1
        if next_frame_number >= self.metadata.frame_count:
            return None
        return self.read_frame_number(next_frame_number)
    def read_frame_number(self, frame_number: int) -> np.ndarray:
        """
        Read a specific frame with caching and access pattern optimization.

        Args:
            frame_number: Frame index to read (0-based)

        Returns:
            Frame as numpy array
        """
        # Validate frame number
        if not 0 <= frame_number < self.metadata.frame_count:
            raise ValueError(
                f"Frame {frame_number} out of bounds [0, {self.metadata.frame_count})"
            )

        # Check cache first
        cached_frame = self.cache.get(frame_number)
        if cached_frame is not None:
            return cached_frame

        # Determine read strategy and read frame
        if self._should_use_sequential_read(frame_number):
            frame = self._read_sequential(frame_number)
        else:
            frame = self._read_random_access(frame_number)

        if frame is None:
            raise RuntimeError(f"Failed to read frame {frame_number}")

        # Cache the frame
        self.cache.put(frame_number, frame)
        self.last_read_frame = frame_number

        return frame

    def _should_use_sequential_read(self, frame_number: int) -> bool:
        """Check if sequential reading would be more efficient."""
        if self.last_read_frame < 0:
            return False

        # If we're reading nearby frames forward, use sequential
        distance = frame_number - self.last_read_frame
        return 0 < distance <= self.sequential_threshold

    def _read_sequential(self, frame_number: int) -> np.ndarray:
        """Read frame using sequential access (grab/retrieve)."""
        # Skip frames using grab() which is faster than read()
        frames_to_skip = frame_number - self.last_read_frame - 1
        for _ in range(frames_to_skip):
            if not self.video_reader.grab():
                raise RuntimeError(f"Failed to grab frame while seeking to {frame_number}")

        # Retrieve the target frame
        ret, frame = self.video_reader.retrieve()
        if not ret or frame is None:
            raise RuntimeError(f"Failed to retrieve frame {frame_number}")

        return frame

    def _read_random_access(self, frame_number: int) -> np.ndarray:
        """Read frame using random access (set position then read)."""
        # Set position and read
        self.video_reader.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.video_reader.read()

        if not ret or frame is None:
            raise RuntimeError(f"Failed to read frame {frame_number}")

        return frame

    def read_frame_batch(self, frame_numbers: list[int]) -> list[np.ndarray]:
        """
        Read multiple frames efficiently.

        Args:
            frame_numbers: List of frame indices to read

        Returns:
            List of frames in the same order as requested
        """
        # Check cache and determine what needs reading
        results = {}
        frames_to_read = []

        for fn in frame_numbers:
            cached = self.cache.get(fn)
            if cached is not None:
                results[fn] = cached
            else:
                frames_to_read.append(fn)

        if frames_to_read:
            # Sort for optimal reading
            frames_to_read.sort()

            # Read missing frames
            for fn in frames_to_read:
                frame = self.read_frame_number(fn)
                results[fn] = frame

        # Return in original order
        return [results[fn] for fn in frame_numbers]

    def get_frame_timestamp(self, frame_number: int) -> float:
        """Get timestamp in seconds for a given frame number."""
        if self.metadata.fps <= 0:
            raise RuntimeError("Invalid FPS value")
        return frame_number / self.metadata.fps

    def get_frame_at_timestamp(self, timestamp_seconds: float) -> np.ndarray:
        """Read frame at specific timestamp."""
        if self.metadata.fps <= 0:
            raise RuntimeError("Invalid FPS value")
        frame_number = int(timestamp_seconds * self.metadata.fps)
        return self.read_frame_number(frame_number)

    def extract_frames_interval(
        self,
        start_frame: int,
        end_frame: int,
        step: int = 1
    ) -> list[np.ndarray]:
        """
        Extract frames from an interval efficiently.

        Args:
            start_frame: Starting frame index
            end_frame: Ending frame index (exclusive)
            step: Step size between frames

        Returns:
            List of extracted frames
        """
        frame_numbers = list(range(start_frame, end_frame, step))
        return self.read_frame_batch(frame_numbers)

    def close(self) -> None:
        """Clean up resources."""
        self.video_reader.release()
        self.cache.clear()

    def __enter__(self) -> "VideoHelper":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


# Example usage
if __name__ == "__main__":
    video_path = Path(r"C:\Users\jonma\Downloads\2025-07-01_ferret_757_EyeCameras_P33_EO5_1m_20s-2m_20s(2).mp4")

    # Using context manager for automatic cleanup
    with VideoHelper.from_video_path(
        video_path,
        cache_size_mb=1000
    ) as vh:
        # Read single frame
        frame = vh.read_frame_number(100)
        print(f"Frame shape: {frame.shape}")

        # Read batch of frames efficiently
        frames = vh.read_frame_batch([10, 50, 100, 150, 200])
        print(f"Read {len(frames)} frames")

        # Extract interval
        interval_frames = vh.extract_frames_interval(0, 100, step=10)
        print(f"Extracted {len(interval_frames)} frames from interval")

        # Get frame at timestamp
        frame_at_5s = vh.get_frame_at_timestamp(5.0)
        print(f"Frame at 5s shape: {frame_at_5s.shape}")