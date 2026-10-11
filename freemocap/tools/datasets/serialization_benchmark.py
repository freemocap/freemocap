"""Measure canonical column construction and validation on a saved reference channel."""
import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.types.channel_kind import ChannelKind


def benchmark(*, recording: Path, output: Path, repeats: int = 3) -> dict:
    if repeats < 1:
        raise ValueError("At least one repetition is required")
    structure = RecordingStructure(base_directory=recording.parent, recording_name=recording.name)
    metadata = read_metadata(path=structure.data_parquet_path)
    run_id = metadata.selected_run_id
    run = metadata.runs[run_id]
    channel = next(channel for channel in run.channels if channel.kind == ChannelKind.RAW_KEYPOINTS_3D)
    saved = read_saved_channel(structure=structure, run_id=run_id, metadata=metadata, channel=channel)
    selected = metadata.model_copy(update={"runs": {run_id: run.model_copy(update={"channels": (channel,)})}})
    sampling = SeriesSampling(frame_numbers=saved.frames, timestamps_s=saved.timestamps_s, run_id=run_id)
    rows = []
    for repetition in range(repeats):
        start = perf_counter()
        batches = list(ChannelSeries(channel=channel, values=saved.values).batches(sampling))
        row = {"construction_seconds": perf_counter() - start}
        states = {}
        # Alternate order to avoid consistently rewarding one path with warmer caches.
        for mode in (("scalar", "columnar") if repetition % 2 == 0 else ("columnar", "scalar")):
            validator = SampleValidator(metadata=selected)
            start = perf_counter()
            for batch in batches:
                if mode == "scalar":
                    validator._accept_rows(batch)
                else:
                    validator.accept(batch=batch)
            validator.finish()
            row[f"{mode}_validation_seconds"] = perf_counter() - start
            states[mode] = (validator.counts, validator.last_samples, validator.timing_digests, validator.pending_rotations)
        if states["scalar"] != states["columnar"]:
            raise ValueError("Columnar validation changed trajectory coverage or timing fingerprints")
        rows.append(row)
    report = dict(recording=str(recording), channel=channel.model_dump(mode="json"),
        frames=len(saved.frames), scalar_rows=int(saved.values.size), repetitions=rows,
        medians={name: median(row[name] for row in rows) for name in rows[0]}, validation_state_equal=True)
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    text = ["RECORDING SERIALIZATION BENCHMARK", f"Recording: {recording}",
        f"{report['frames']} frames; {report['scalar_rows']} scalar rows in one 3D channel.",
        "Input loading is excluded. All scientific checks remain enabled."]
    text.extend(f"{name}: {seconds:.6f} s (median of {repeats})" for name, seconds in report["medians"].items())
    text.append("Coverage, exact timestamp/frame digests and validation state match the scalar path.")
    (output / "report.txt").write_text("\n".join(text) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    report = benchmark(recording=args.recording, output=args.output, repeats=args.repeats)
    print(json.dumps(report["medians"], indent=2))


if __name__ == "__main__":
    main()
