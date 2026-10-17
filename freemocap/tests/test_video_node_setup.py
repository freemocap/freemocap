"""Setup failures must report failure, stop the pipeline, and release resources."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from freemocap.core.pipeline.posthoc import video_node as module


@pytest.mark.parametrize('failure', ['tracker', 'cache', 'open', 'metadata'])
def test_video_setup_failure_reports_and_cleans_up(monkeypatch, failure):
    tracker = Mock()
    reader = Mock()
    reader.isOpened.return_value = failure != 'open'
    reader.get.side_effect = RuntimeError('metadata failed') if failure == 'metadata' else None
    build = Mock(return_value=tracker)
    cache = Mock(return_value=None)
    if failure == 'tracker':
        build.side_effect = RuntimeError('tracker failed')
    if failure == 'cache':
        cache.side_effect = RuntimeError('cache failed')
    monkeypatch.setattr(module, 'build_configured_tracker', build)
    monkeypatch.setattr(module, '_build_recording_frame_cache', cache)
    monkeypatch.setattr(module.cv2, 'VideoCapture', Mock(return_value=reader))
    progress = Mock()
    output = Mock()
    ipc = Mock(should_continue=True)
    module.VideoNode._run(camera_id='camera', video_path=Path('/tmp/camera.mp4'),
        detector_config=Mock(), ipc=ipc, video_output_pub=output,
        video_progress_pub=progress, shutdown_self_flag=SimpleNamespace(value=False),
        recording_path=Path('/tmp/recording'), save_annotated_video=False,
        annotation_input=module.AnnotationInput.RAW, pipeline_id='setup-test',
        pipeline_type=module.PosthocPipelineType.CALIBRATION)
    messages = [call.args[0] for call in progress.put.call_args_list]
    assert messages[-1].phase == module.VideoNodePhase.FAILED
    assert messages[-1].progress_fraction == 0.0
    assert all(message.phase != module.VideoNodePhase.COMPLETE for message in messages)
    ipc.shutdown_pipeline.assert_called_once_with()
    output.put.assert_not_called()
    if failure == 'tracker':
        tracker.close.assert_not_called()
    else:
        tracker.close.assert_called_once_with()
    if failure in ('open', 'metadata'):
        reader.release.assert_called_once_with()
    else:
        reader.release.assert_not_called()


@pytest.mark.parametrize('outcome', ['complete', 'truncated', 'cancelled'])
def test_video_publication_requires_complete_processing(monkeypatch, outcome):
    tracker, reader, annotation = Mock(), Mock(), Mock()
    reader.isOpened.return_value = True
    frame_count = 2 if outcome == 'truncated' else 1
    metadata = {module.cv2.CAP_PROP_FRAME_COUNT: frame_count,
                module.cv2.CAP_PROP_FPS: 30, module.cv2.CAP_PROP_FRAME_WIDTH: 640,
                module.cv2.CAP_PROP_FRAME_HEIGHT: 480}
    reader.get.side_effect = metadata.__getitem__
    reader.read.side_effect = [(True, object()), (False, None)]
    monkeypatch.setattr(module, 'build_configured_tracker', Mock(return_value=tracker))
    monkeypatch.setattr(module, '_build_recording_frame_cache', Mock(return_value=None))
    monkeypatch.setattr(module.cv2, 'VideoCapture', Mock(return_value=reader))
    monkeypatch.setattr(module, 'build_observation_annotator', Mock())
    monkeypatch.setattr(module, 'AnnotationVideoOutput', Mock(return_value=annotation))
    monkeypatch.setattr(module, '_get_observation', Mock(return_value=(Mock(), Mock())))
    progress, ipc = Mock(), Mock(should_continue=True)
    module.VideoNode._run(camera_id='camera', video_path=Path('/tmp/camera.mp4'),
        detector_config=Mock(), ipc=ipc, video_output_pub=Mock(),
        video_progress_pub=progress, shutdown_self_flag=SimpleNamespace(value=outcome == 'cancelled'),
        recording_path=Path('/tmp/recording'), save_annotated_video=True,
        annotation_input=module.AnnotationInput.RAW, pipeline_id='processing-test',
        pipeline_type=module.PosthocPipelineType.CALIBRATION)
    phases = [call.args[0].phase for call in progress.put.call_args_list]
    if outcome == 'complete':
        annotation.publish.assert_called_once_with()
        assert phases[-1] == module.VideoNodePhase.COMPLETE
        ipc.shutdown_pipeline.assert_not_called()
    else:
        annotation.publish.assert_not_called()
        assert module.VideoNodePhase.COMPLETE not in phases
        if outcome == 'truncated':
            assert phases[-1] == module.VideoNodePhase.FAILED
            ipc.shutdown_pipeline.assert_called_once_with()
    annotation.close.assert_called_once_with()
    tracker.close.assert_called_once_with()
    reader.release.assert_called_once_with()
