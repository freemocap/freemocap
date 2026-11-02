"""Built-in server outputs; protocol dependencies never hide runtime failures."""
from freemocap.core.streaming.outputs.contracts import ProtocolDefinition
from freemocap.core.streaming.outputs.lsl import LslConfig, LslEmitter, lsl_unavailable_reason
from freemocap.core.streaming.outputs.vmc import VmcConfig, VmcEmitter


def builtin_protocols() -> tuple[ProtocolDefinition, ...]:
    return (ProtocolDefinition("vmc", VmcConfig, VmcEmitter, "latest"),
            ProtocolDefinition("lsl", LslConfig, LslEmitter, "fail", lsl_unavailable_reason))
