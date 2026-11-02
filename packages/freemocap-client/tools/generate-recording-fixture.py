"""Create the tiny, hand-specified reader fixture with independent PyArrow encoding.

Requires pyarrow; writes only the requested output file. Expected values in the
JavaScript test are authored separately, not copied from decoder output.
"""
import base64
import json
import sys
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

channels = [
    dict(sensor_group="eye", source="device", reference_frame=None,
         stage="observations", kind="PUPIL_DIAMETER", names=["right", "left"], components={"diameter": "mm"}),
    dict(sensor_group="body", source="probe", reference_frame="world",
         stage="reconstruction", kind="LANDMARKS_3D", names=["tip"], components={"z": "mm", "x": "mm", "y": "mm"}),
]
# Deliberately shuffled frames/names/components; null means missing, not zero.
samples = [(0, 11, "right", "diameter", 4., .108), (0, 10, "left", "diameter", 2., .100),
           (0, 11, "left", "diameter", None, .108), (0, 10, "right", "diameter", 3., .100),
           (1, 2, "tip", "y", 2., 1.), (1, 2, "tip", "x", 1., 1.), (1, 2, "tip", "z", 3., 1.)]
rows = []
for index, frame, name, component, value, time in samples:
    channel = channels[index]
    rows.append(dict(run_id=0, sensor_group=channel["sensor_group"], source=channel["source"],
                     reference_frame=channel["reference_frame"], channel=channel["kind"],
                     frame_number=frame, name=name, component=component, units="mm", timestamp_s=time, value=value))
schema = pa.schema([(name, pa.int64() if name in ("run_id", "frame_number") else
                     pa.float64() if name in ("timestamp_s", "value") else pa.string()) for name in rows[0]])
output = pa.BufferOutputStream()
pq.write_table(pa.Table.from_pylist(rows, schema=schema), output, compression="zstd", row_group_size=3)
manifest = dict(recording_id="reader-fixture", revision="authored-fixture-v1", selected_run_id=0,
                runs=[dict(run_id=0, model_sources={}, models=[], channels=channels,
                           static_channels=[], timelines=[], media=[])])
Path(sys.argv[1]).write_text(json.dumps(dict(pyarrow_version=pa.__version__, manifest=manifest,
    parquet_base64=base64.b64encode(output.getvalue().to_pybytes()).decode("ascii")), indent=2)+"\n", encoding="utf-8")
