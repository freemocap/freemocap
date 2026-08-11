"""Standard-stream wire contract: schema (StreamInfo) + sample (binary) + codecs.

WS-1 — pure contract + codecs, no pipeline / WebSocket wiring. The SSOT for the
wire format used by the backend encoder (WS-2), the UI decoder (WS-4), and the
LSL route. See
[09 — Standard Stream Protocol](docs/streaming-compatibility/09-standard-stream-protocol.md)
and [WS-1 plan](docs/streaming-compatibility/phase-1/01-standard-stream-contract.md).
"""
from freemocap.core.streaming.standard_stream.coordinate_convention import (
    FREEMOCAP_CANONICAL_CONVENTION,
    Axis,
    CoordinateConvention,
    Handedness,
    RotationForm,
    RotationFrame,
    Units,
)
from freemocap.core.streaming.standard_stream.lsl_bridge import (
    sample_to_flat_vector,
    schema_to_streaminfo_channels,
)
from freemocap.core.streaming.standard_stream.stream_sample import (
    BLOCK_HEADER_DTYPE,
    BLOCK_HEADER_SIZE,
    SAMPLE_FOOTER_SIZE,
    SAMPLE_HEADER_DTYPE,
    SAMPLE_HEADER_SIZE,
    DtypeCode,
    MessageType,
    SampleBlock,
    StreamSample,
    decode_sample,
    encode_sample,
)
from freemocap.core.streaming.standard_stream.stream_schema import (
    ChannelGroup,
    ChannelKind,
    RestPose,
    StreamSchema,
    decode_schema,
    encode_schema,
)
from freemocap.core.streaming.standard_stream.stream_schema_builder import (
    DEFAULT_DERIVED_POINTS,
    build_stream_schema,
)

__all__ = [
    # coordinate convention
    "Units", "Handedness", "Axis", "RotationFrame", "RotationForm",
    "CoordinateConvention", "FREEMOCAP_CANONICAL_CONVENTION",
    # schema
    "ChannelKind", "ChannelGroup", "RestPose", "StreamSchema",
    "encode_schema", "decode_schema",
    "build_stream_schema", "DEFAULT_DERIVED_POINTS",
    # sample
    "MessageType", "DtypeCode", "SampleBlock", "StreamSample",
    "encode_sample", "decode_sample",
    "SAMPLE_HEADER_DTYPE", "BLOCK_HEADER_DTYPE",
    "SAMPLE_HEADER_SIZE", "BLOCK_HEADER_SIZE", "SAMPLE_FOOTER_SIZE",
    # lsl
    "schema_to_streaminfo_channels", "sample_to_flat_vector",
]
