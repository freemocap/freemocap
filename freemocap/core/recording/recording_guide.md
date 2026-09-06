# Recording package guide

A recording describes a capture volume. Its subjects, trackers and scientific models describe
particular measurement sources. Capture metadata JSON is separate from the descriptor in Parquet.

## Folder map

```text
recording/
    recording_guide.md
    playback_queries.py
    data_descriptors/
        recording_descriptor.py
        model_definition.py
        camera_geometry.py
        scale_fit.py
        sample_conventions.py
    sample_encoding/
        arrow_schema.py
        channel_series.py
        spatial_points.py
        observation_samples.py
        reconstruction_samples.py
        fit_channels.py
    parquet_storage/
        parquet_reader.py
        parquet_writer.py
        shared_file.py
        checkpoint_publication.py
    result_processing/
        observation_inputs.py
        observation_publication.py
        input_signatures.py
        saved_reconstruction.py
        reconstruction_completion.py
```

Python packages also contain the required `__init__.py` files, with no forwarding imports.

## Read in this order

1. **data_descriptors**: what the saved data means. Start with `recording_descriptor.py` for
   runs, sources, channels and their validation; then inspect the model and geometry definitions.
2. **sample_encoding**: how observations and numerical results become tall Arrow rows. Start
   with `arrow_schema.py` for columns and validation, then `channel_series.py` for serialization.
3. **parquet_storage**: how files are read and atomically published. `checkpoint_publication.py`
   preserves retained rows and merges replacement stage outputs into the published file.
4. **result_processing**: how processing results become a recording publication, and how saved
   inputs are prepared for another computation. `observation_inputs.py` defines the request;
   `observation_publication.py` assembles its descriptors and batches. `input_signatures.py`
   identifies inputs; `saved_reconstruction.py` reloads them. `reconstruction_completion.py`
   records evidence that numerical stages completed; it does not perform file publication.
5. **playback_queries.py**: manifests and bounded timestamp queries over the saved recording.
   This is a single consumer module, so it lives directly under `recording`.

## Ownership

Scientific calculations belong in SkellyForge, detection in SkellyTracker, and camera media/timing
in SkellyCam. This package describes, serializes, publishes and reads their results. Publication
writes only the canonical Parquet; it does not write measurements into recording metadata JSON.

The current column layout and serialized descriptors are preserved. Review the descriptor and
encoding contracts before designing additional output formats.
