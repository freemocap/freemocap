"""Measure bounded column batches through the production Parquet disk writer."""
import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from freemocap.core.recording.sample_encoding.arrow_schema import SAMPLE_SCHEMA, SampleValidator
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.parquet_storage.parquet_writer import publish_parquet
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def scalar_batches(channel, saved, sampling):
    """Diagnostic row-dictionary baseline with the same frame-aligned boundaries."""
    width = len(channel.names) * len(channel.components)
    limit = (sampling.batch_size // width) * width or sampling.batch_size
    rows = []
    for index, (frame, timestamp) in enumerate(zip(saved.frames, saved.timestamps_s, strict=True)):
        for point, name in enumerate(channel.names):
            for axis, (component, units) in enumerate(channel.components.items()):
                value = float(saved.values[index, point, axis])
                rows.append(dict(timestamp_s=timestamp, sensor_group=channel.sensor_group,
                    frame_number=frame, source=channel.source, reference_frame=channel.reference_frame,
                    channel=channel.kind, name=name, component=component,
                    value=None if np.isnan(value) else value, units=units, run_id=sampling.run_id))
                if len(rows) == limit:
                    yield pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)
                    rows.clear()
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)


def benchmark(*, recording: Path, output: Path, repeats: int = 3, construction: str = "columns") -> dict:
    if repeats < 1:
        raise ValueError("At least one repetition is required")
    if construction not in ("rows", "columns"):
        raise ValueError("Choose rows or columns")
    output.mkdir(parents=True, exist_ok=False)
    structure = RecordingStructure(base_directory=recording.parent, recording_name=recording.name)
    metadata = read_metadata(path=structure.data_parquet_path)
    run_id = metadata.selected_run_id
    run = metadata.runs[run_id]
    channel = next(c for c in run.channels if c.kind == ChannelKind.RAW_KEYPOINTS_3D)
    saved = read_saved_channel(structure=structure, run_id=run_id, metadata=metadata, channel=channel)
    selected = metadata.model_copy(update={"runs": {run_id: run.model_copy(update={"channels": (channel,)})}})
    rows = []
    sizes = (16384, 65536, 262144, 1048576)
    for repetition in range(repeats):
        for size in sizes[repetition % 4:] + sizes[:repetition % 4]:
            path = output / f"batch-{size}-repeat-{repetition}.parquet"
            validator = SampleValidator(metadata=selected)
            timings = {"construction_seconds": 0.0, "validation_seconds": 0.0}
            batch_count = 0
            def batches():
                nonlocal batch_count
                sampling = SeriesSampling(frame_numbers=saved.frames, timestamps_s=saved.timestamps_s,
                                          run_id=run_id, batch_size=size)
                iterator = iter(scalar_batches(channel, saved, sampling) if construction == "rows"
                    else ChannelSeries(channel=channel, values=saved.values).batches(sampling))
                while True:
                    started = perf_counter()
                    batch = next(iterator, None)
                    timings["construction_seconds"] += perf_counter() - started
                    if batch is None:
                        break
                    started = perf_counter()
                    validator.accept(batch=batch)
                    timings["validation_seconds"] += perf_counter() - started
                    batch_count += 1
                    yield batch
                started = perf_counter()
                validator.finish()
                timings["validation_seconds"] += perf_counter() - started
            started = perf_counter()
            publish_parquet(path=path, schema=SAMPLE_SCHEMA, batches=batches())
            total_write = perf_counter()-started
            started = perf_counter()
            table = pq.read_table(path)
            read_seconds = perf_counter()-started
            # Compare actual saved scalar values and complete validation state.
            np.testing.assert_array_equal(table["value"].to_numpy(), saved.values.reshape(-1))
            read_validator = SampleValidator(metadata=selected)
            for batch in table.to_batches():
                read_validator.accept(batch=batch)
            read_validator.finish()
            for name in ("counts", "last_samples", "timing_digests", "pending_rotations"):
                if getattr(validator, name) != getattr(read_validator, name):
                    raise ValueError(f"Readback changed {name}")
            row = dict(batch_size=size, repetition=repetition, batches=batch_count,
                write_total_seconds=total_write, read_seconds=read_seconds,
                writer_remainder_seconds=total_write-sum(timings.values()),
                bytes=path.stat().st_size, **timings)
            rows.append(row)
            print(f"{size}: write {total_write:.3f} s, read {read_seconds:.3f} s; parity passed", flush=True)
    medians = {str(size): {key: median(row[key] for row in rows if row["batch_size"] == size)
        for key in ("construction_seconds", "validation_seconds", "writer_remainder_seconds", "write_total_seconds", "read_seconds", "bytes")}
        for size in sizes}
    report = dict(recording=str(recording), construction=construction, frames=len(saved.frames), scalar_rows=saved.values.size,
        measurements=rows, medians=medians, parity=True)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["PARQUET BATCH SIZE COMPARISON", f"Construction: {construction}", f"{len(saved.frames)} frames; {saved.values.size} scalar rows",
        "Production zstd writer, fsync and atomic replacement; bounded generation, no whole-recording staging.",
        "Readbacks use warm OS cache. Writer remainder includes compression and filesystem work, not pure disk time.",
        "Exact values, coverage and timing digests passed; measurements exclude readback verification.",
        "Rows/batch | build s | validate s | writer remainder s | total write s | read s | bytes"]
    for size, values in medians.items():
        lines.append(size + " | " + " | ".join(f"{v:.6f}" for v in values.values()))
    (output / "report.txt").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--construction", choices=("rows", "columns"), default="columns")
    args = parser.parse_args()
    benchmark(recording=args.recording, output=args.output, repeats=args.repeats, construction=args.construction)
