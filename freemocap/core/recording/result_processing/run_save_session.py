"""One processing destination shared by all checkpoint and file sinks.

Starting a new attempt reserves its output folder. A Parquet run appears only at
the first successful checkpoint. Later checkpoints update that same run.
Call check/accept while holding the existing recording write lock.
"""
from dataclasses import dataclass
from typing import Literal

from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata


@dataclass
class RunSaveSession:
    source_run_id: int
    target_run_id: int
    expected_metadata: RecordingMetadata | None
    published: bool = False

    @classmethod
    def resolve(cls, *, structure, source_run_id: int, mode: Literal['overwrite', 'new_run']):
        if mode not in ('overwrite', 'new_run'):
            raise ValueError('Choose overwrite or new_run')
        metadata = read_metadata(path=structure.data_parquet_path) if structure.data_parquet_path.exists() else None
        if metadata is not None and source_run_id not in metadata.runs:
            raise ValueError(f'Saved run {source_run_id} does not exist')
        if metadata is None and source_run_id != 0:
            raise ValueError('A recording without saved results starts at Run 0')
        target = max(metadata.runs) + 1 if metadata is not None and mode == 'new_run' else source_run_id
        if metadata is not None and mode == 'new_run':
            # Atomic directory creation reserves the ID even if annotation succeeds
            # before a failed scientific save. Never reuse failed attempts' outputs.
            roots = (structure.exports_dir, structure.full_path, structure.full_path / 'annotated_videos')
            occupied = [int(path.name[4:]) for root in roots for path in root.glob('run-*')
                        if path.name[4:].isdigit()]
            target = max(target, max(occupied, default=-1) + 1)
            structure.exports_dir.mkdir(parents=True, exist_ok=True)
            while True:
                try:
                    (structure.exports_dir / f'run-{target}').mkdir()
                    break
                except FileExistsError:
                    target += 1
        return cls(source_run_id, target, metadata)

    @property
    def base_run_id(self) -> int:
        return self.target_run_id if self.published else self.source_run_id

    def check(self, metadata: RecordingMetadata | None) -> None:
        if metadata != self.expected_metadata:
            raise ValueError('Recording changed after selecting the processing run; reload and try again')

    def accept(self, metadata: RecordingMetadata) -> RecordingMetadata:
        self.expected_metadata = metadata
        self.published = True
        return metadata
