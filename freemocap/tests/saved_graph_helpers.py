"""Run the production application graph against test-owned saved recordings."""
from concurrent.futures import CancelledError
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.dataflow.application_pipeline import run_application_graph
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapWorkerRequest
from freemocap.core.recording.exports.requests import ExportOptions


def run_saved_graph(*, structure, config, reporter, cancelled=None):
    if cancelled and cancelled():
        raise CancelledError()
    request = MocapWorkerRequest(pipeline_id="saved-graph-test",
        recording=RecordingInfo(recording_name=structure.recording_name,
                                recording_directory=str(structure.base_directory)),
        config=config.model_copy(update={'export_to_blender': False, 'export_tall_csv': False,
                                         'export_options': ExportOptions()}),
        ipc=Mock(spec=PipelineIPC, should_continue=True,
                 pipeline_shutdown_flag=SimpleNamespace(value=False)), progress_queue=Queue())
    run_application_graph(request=request)
