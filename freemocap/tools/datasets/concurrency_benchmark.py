"""Compare real saved-recording work under serial, thread and process execution.

This is a diagnostic, not a production scheduler. Workers read the same immutable
recording independently; end-to-end times include pool startup and input loading.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path
from statistics import median
from time import perf_counter


def recording_work(recording: str, operation: str) -> dict:
    started = perf_counter()
    import pyarrow.parquet as pq
    from pydantic import TypeAdapter
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
    from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator
    from freemocap.core.recording.result_processing.saved_reconstruction import (
        read_saved_reconstruction, SavedReconstructionRequest, SavedPointPolicy,
    )
    from freemocap.core.reconstruction.posthoc_reconstruction import fit_skeletons_for_recording
    from freemocap.core.reconstruction.recording_fit import FittedRecordingScale
    from freemocap.system.recording_structure.recording_structure import RecordingStructure

    path = Path(recording)
    structure = RecordingStructure(base_directory=path.parent, recording_name=path.name)
    metadata = read_metadata(path=structure.data_parquet_path)
    run_id = metadata.selected_run_id
    if operation == "fit":
        run = metadata.runs[run_id]
        fit = run.scale_fits[0]
        source = run.sources[fit.source].definition
        saved = read_saved_reconstruction(SavedReconstructionRequest(
            structure=structure, run_id=run_id, sensor_group=fit.sensor_group,
            point_source=source["tracker"], model_id=source["model_id"],
            point_policy=SavedPointPolicy.FILTERED, compute_center_of_mass=True))
        ready = perf_counter()
        result = fit_skeletons_for_recording(saved.numerical_input)
        finished = perf_counter()
        evidence = TypeAdapter(dict[str, FittedRecordingScale]).dump_python(result, mode="json")
        # These two fields are declared frozensets, not ordered scientific axes.
        # Spawned interpreters legitimately serialize their iteration order differently.
        for fitted in evidence.values():
            if fitted["fit"] is not None:
                for name in ("measured_segment_names", "voting_segment_names"):
                    fitted["fit"][name] = sorted(fitted["fit"][name])
        payload = json.dumps(evidence, sort_keys=True)
    elif operation == "validate":
        batches = list(pq.ParquetFile(structure.data_parquet_path).iter_batches(batch_size=65536))
        ready = perf_counter()
        validator = SampleValidator(metadata=metadata)
        for batch in batches:
            validator.accept(batch=batch)
        validator.finish()
        finished = perf_counter()
        # Stable ordering, preserving exact digest bytes and float representations.
        payload = repr(tuple(sorted(state.items(), key=lambda item: repr(item[0])) for state in (
            validator.counts, validator.last_samples, validator.timing_digests,
            validator.pending_rotations)))
    else:
        raise ValueError(f"Unknown operation: {operation}")
    return dict(operation=operation, setup_seconds=ready-started,
        work_seconds=finished-ready,
        fingerprint=hashlib.sha256(payload.encode()).hexdigest(), evidence=payload)


def benchmark(*, recording: Path, output: Path, repeats: int = 3) -> dict:
    if repeats < 1:
        raise ValueError("At least one repetition is required")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    expected = {}
    modes = ("serial", "threads", "processes")
    for repetition in range(repeats):
        for mode in modes[repetition % 3:] + modes[:repetition % 3]:
            started = perf_counter()
            if mode == "serial":
                results = [recording_work(str(recording), op) for op in ("fit", "validate")]
            else:
                pool_type = ThreadPoolExecutor if mode == "threads" else ProcessPoolExecutor
                options = {} if mode == "threads" else {"mp_context": multiprocessing.get_context("spawn")}
                with pool_type(max_workers=2, **options) as pool:
                    futures = [pool.submit(recording_work, str(recording), op) for op in ("fit", "validate")]
                    results = [future.result() for future in futures]
            row = dict(mode=mode, repetition=repetition, wall_seconds=perf_counter()-started, workers=results)
            rows.append(row)
            (output / "measurements.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            for result in results:
                key = result["operation"]
                expected.setdefault(key, result["fingerprint"])
                if result["fingerprint"] != expected[key]:
                    raise ValueError(f"Scientific output changed under {mode}: {key}")
            print(f"{mode}: {row['wall_seconds']:.3f} s; exact fingerprints match", flush=True)
            (output / "measurements.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    report = dict(recording=str(recording), repetitions=rows, exact_parity=True,
        median_wall_seconds={mode: median(row["wall_seconds"] for row in rows if row["mode"] == mode) for mode in modes})
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["SAVED RECORDING CONCURRENCY COMPARISON", str(recording),
        "Two jobs: model fitting and complete saved-file validation.",
        "Includes input reads, worker imports, pool startup and shutdown; OS caches are not cleared.",
        "Fresh process pools each repetition; this does not measure a persistent warm pool.",
        "No image arrays cross process boundaries. Exact fit and validator fingerprints match."]
    lines.extend(f"{mode}: {value:.3f} s median ({repeats} repetitions)" for mode, value in report["median_wall_seconds"].items())
    (output / "report.txt").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    benchmark(recording=args.recording.resolve(), output=args.output, repeats=args.repeats)


if __name__ == "__main__":
    main()
