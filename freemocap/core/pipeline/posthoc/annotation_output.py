"""Frame-preserving annotation encoding and publication for recording videos."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from skellycam.core.recorders.videos.pyav_video_writer import PyavVideoWriter
from skellytracker.core.annotation.keypoint_annotator import KeypointAnnotator
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.posthoc.annotation_input import AnnotationInput
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.system.default_paths import ANNOTATED_VIDEOS_FOLDER_NAME


@dataclass(frozen=True, slots=True)
class AnnotationOutputRequest:
    recording_path: Path
    pipeline_id: str
    video: VideoMetadata
    input_mode: AnnotationInput


class AnnotationVideoOutput:
    def __init__(self, request: AnnotationOutputRequest) -> None:
        self.request = request
        directory = request.recording_path / ANNOTATED_VIDEOS_FOLDER_NAME
        directory.mkdir(parents=True, exist_ok=True)
        source = request.video.file_path
        self.destination = directory / f"{source.stem}_annotated{source.suffix}"
        self.temporary = directory / f".{source.stem}.{request.pipeline_id}.partial{source.suffix}"
        self.writer: PyavVideoWriter | None = None
        self.base_reader: cv2.VideoCapture | None = None
        self.frames_written = 0
        try:
            if request.input_mode == AnnotationInput.ANNOTATED:
                if not self.destination.is_file():
                    raise FileNotFoundError(f"Annotated input does not exist: {self.destination}")
                self.base_reader = cv2.VideoCapture(str(self.destination), cv2.CAP_FFMPEG)
                if not self.base_reader.isOpened():
                    raise RuntimeError(f"Cannot open annotated input: {self.destination}")
                if int(self.base_reader.get(cv2.CAP_PROP_FRAME_COUNT)) != request.video.frame_count:
                    raise ValueError("Annotated input frame count does not match raw video")
            self.writer = PyavVideoWriter(
                path=str(self.temporary), fps=request.video.fps,
                width=request.video.width, height=request.video.height,
            )
        except Exception:
            self.close()
            raise

    def write_frame(
        self, *, image: NDArray[np.uint8], observation: Observation, annotator: KeypointAnnotator,
    ) -> None:
        if self.writer is None:
            raise RuntimeError("Annotation output is closed")
        if observation.frame_number != self.frames_written:
            raise ValueError("Annotation frames must be written in contiguous recording order")
        if self.base_reader is not None:
            success, image = self.base_reader.read()
            if not success or image is None:
                raise RuntimeError(f"Annotated input ends before frame {self.frames_written}: {self.destination}")
        self.writer.write(annotator.annotate(image=image, observation=observation))
        self.frames_written += 1

    def publish(self) -> None:
        if self.frames_written != self.request.video.frame_count:
            raise ValueError("Cannot publish an incomplete annotated video")
        if self.writer is None:
            raise RuntimeError("Annotation output is closed")
        self.writer.release()
        self.writer = None
        if self.base_reader is not None:
            self.base_reader.release()
            self.base_reader = None
        self.temporary.replace(self.destination)

    def close(self) -> None:
        try:
            if self.writer is not None:
                self.writer.release()
                self.writer = None
        finally:
            if self.base_reader is not None:
                self.base_reader.release()
                self.base_reader = None
            if self.temporary.exists():
                self.temporary.unlink()
