import multiprocessing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import av
import numpy as np
from skellycam.core.recorders.videos.pyav_video_writer import PyavVideoWriter
from skellytracker.core import TrackerConfig
from skellytracker.core.annotation.keypoint_annotator import KeypointAnnotator
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.annotation_input import AnnotationInput
from freemocap.core.pipeline.posthoc.pipeline_phases import PosthocPipelineType
from freemocap.core.pipeline.posthoc.video_node import VideoNode


class AnnotationVideoEncodingTests(unittest.TestCase):
    def test_raw_regeneration_and_explicit_layering_encode_h264(self) -> None:
        for mode in AnnotationInput:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                raw = folder / "camera.mp4"
                annotated = folder / "annotated_videos" / "camera_annotated.mp4"
                annotated.parent.mkdir()
                for path, value in ((raw, 60), (annotated, 180)):
                    writer = PyavVideoWriter(path=str(path), fps=30.0, width=64, height=64)
                    writer.write(np.full((64, 64, 3), value, dtype=np.uint8))
                    writer.release()
                ipc = Mock(spec=PipelineIPC)
                ipc.should_continue = True
                queues = [multiprocessing.Queue(), multiprocessing.Queue()]
                renderer = Mock(spec=KeypointAnnotator)
                renderer.annotate.side_effect = lambda image, observation: image
                try:
                    with patch("freemocap.core.pipeline.posthoc.video_node.build_configured_tracker"), patch("freemocap.core.pipeline.posthoc.video_node._build_recording_frame_cache", return_value=None), patch("freemocap.core.pipeline.posthoc.video_node.build_observation_annotator", return_value=renderer), patch("freemocap.core.pipeline.posthoc.video_node._get_observation", return_value=(Observation(frame_number=0, image_size=(64, 64)), TrackerState())):
                        VideoNode._run(camera_id="camera", video_path=raw, detector_config=TrackerConfig(stages=[]),
                            ipc=ipc, video_output_pub=queues[0], video_progress_pub=queues[1],
                            shutdown_self_flag=multiprocessing.Value('b', False), recording_path=folder,
                            save_annotated_video=True, annotation_input=mode,
                            pipeline_id="test", pipeline_type=PosthocPipelineType.CALIBRATION)
                    ipc.shutdown_pipeline.assert_not_called()
                    with av.open(str(annotated)) as container:
                        self.assertEqual(container.streams.video[0].codec_context.name, "h264")
                        frames = list(container.decode(video=0))
                        self.assertEqual(len(frames), 1)
                        mean = frames[0].to_ndarray(format="bgr24").mean()
                        self.assertAlmostEqual(mean, 60 if mode == AnnotationInput.RAW else 180, delta=8)
                    self.assertFalse(list(annotated.parent.glob("*.partial*")))
                finally:
                    for queue in queues:
                        queue.close()
                        queue.join_thread()
