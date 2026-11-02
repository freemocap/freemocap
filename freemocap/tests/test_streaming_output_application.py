from types import SimpleNamespace

import pytest

from freemocap.app.freemocap_application import FreemocapApplication
from freemocap.core.streaming.outputs.registry import builtin_protocols


def test_builtin_protocols_declare_different_delivery_policies_without_opening_transports():
    definitions = {item.name: item for item in builtin_protocols()}
    assert definitions["vmc"].overflow_policy == "latest"
    assert definitions["lsl"].overflow_policy == "fail"
    assert "host" in definitions["vmc"].config_type.model_json_schema()["properties"]


@pytest.mark.parametrize("output_failure", [False, True])
def test_application_closes_outputs_before_capture_and_still_cleans_up_on_error(output_failure):
    calls = []
    def stop_outputs():
        calls.append("outputs")
        if output_failure:
            raise RuntimeError("output cleanup failed")
    app = object.__new__(FreemocapApplication)
    app.global_kill_flag = SimpleNamespace(value=False)
    app.streaming_outputs = SimpleNamespace(close=stop_outputs)
    app.realtime_pipeline_manager = SimpleNamespace(shutdown=lambda: calls.append("realtime"))
    app.posthoc_pipeline_manager = SimpleNamespace(shutdown=lambda: calls.append("posthoc"))
    app.sync_job_manager = SimpleNamespace(shutdown=lambda: calls.append("sync"))
    app.inference_service = SimpleNamespace(close=lambda: calls.append("inference"))
    if output_failure:
        with pytest.raises(RuntimeError, match="output cleanup failed"):
            app.close()
    else:
        app.close()
    assert calls == ["outputs", "realtime", "posthoc", "sync", "inference"]
    assert app.global_kill_flag.value is True
