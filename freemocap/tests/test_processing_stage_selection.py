"""Unsupported finish points must never be silently ignored by the API config."""
import pytest
from pydantic import ValidationError

from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def test_legacy_partial_request_cannot_silently_run_to_completion():
    with pytest.raises(ValidationError, match='stopStage'):
        PosthocMocapPipelineConfig.model_validate({
            'pipelineImplementation': 'current', 'stopStage': 'filtering',
        })


@pytest.mark.parametrize('stop', ['observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction'])
def test_graph_accepts_implemented_finish_points(stop):
    config = PosthocMocapPipelineConfig.model_validate({'stopStage': stop})
    assert config.stop_stage == stop


def test_reversed_stage_range_is_rejected():
    with pytest.raises(ValidationError, match='must not precede'):
        PosthocMocapPipelineConfig(startStage='triangulation', stopStage='observations')


def test_run_save_mode_is_explicit_and_legacy_cannot_ignore_it():
    assert PosthocMocapPipelineConfig(runSaveMode='new_run').run_save_mode == 'new_run'
    assert PosthocMocapPipelineConfig().run_save_mode == 'overwrite'
    with pytest.raises(ValidationError):
        PosthocMocapPipelineConfig(runSaveMode='keep_typo')
    with pytest.raises(ValidationError, match='Creating a processing run'):
        PosthocMocapPipelineConfig(pipelineImplementation='current', runSaveMode='new_run')
