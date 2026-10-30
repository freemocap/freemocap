"""Select complete scientific channels from one caller-owned recording file."""

from collections.abc import Callable, Iterator
from concurrent.futures import CancelledError
from dataclasses import dataclass

import pyarrow as pa
import pyarrow.compute as pc

from freemocap.core.recording.parquet_storage.recording_view import RecordingView


@dataclass(frozen=True)
class ChannelQuery:
    """A complete stored channel identity, including its run and null reference."""

    run_id: int
    sensor_group: str
    source: str
    channel_kind: str
    reference_frame: str | None

    @property
    def filter_values(self) -> tuple[tuple[str, int | str | None], ...]:
        return (
            ("run_id", self.run_id),
            ("sensor_group", self.sensor_group),
            ("source", self.source),
            ("channel", self.channel_kind),
            ("reference_frame", self.reference_frame),
        )


@dataclass(frozen=True)
class RunQuery:
    """Every row in one run/group, including undeclared channel identities.

    Checkpoint retention must copy these rows so publication validation can
    reject corrupt input instead of silently dropping undeclared channels.
    """

    run_id: int
    sensor_group: str

    @property
    def filter_values(self) -> tuple[tuple[str, int | str | None], ...]:
        return (("run_id", self.run_id), ("sensor_group", self.sensor_group))


@dataclass(frozen=True)
class ComponentQuery:
    """One stored component across all identities, including undeclared ones."""

    channel_kind: str
    component: str

    @property
    def filter_values(self) -> tuple[tuple[str, str], ...]:
        return (("channel", self.channel_kind), ("component", self.component))


def selected_batches(
    view: RecordingView,
    queries: tuple[ChannelQuery | RunQuery | ComponentQuery, ...],
    *,
    columns: tuple[str, ...] | None = None,
    batch_size: int = 65536,
    cancelled: Callable[[], bool] | None = None,
) -> Iterator[pa.RecordBatch]:
    """Read the union of queries once, retaining file order and row-group bounds.

    Missing statistics never prove exclusion: those groups are decoded and
    filtered. Projection retains identity columns needed for filtering, matching
    the export reader's existing contract. Unknown identities return no rows;
    callers that require available channels validate against view.metadata first.
    The caller owns the open view throughout iteration; this function never opens
    another file. Duplicate queries do not duplicate selected rows.
    """
    if batch_size < 1:
        raise ValueError("Parquet batch size must be positive")

    def check_cancelled() -> None:
        if cancelled is not None and cancelled():
            raise CancelledError("Recording read cancelled")

    check_cancelled()
    filter_sets = tuple(query.filter_values for query in dict.fromkeys(queries))
    schema = view.parquet.schema_arrow
    read_columns = None
    if columns is not None:
        unknown = set(columns) - set(schema.names)
        if unknown:
            raise ValueError(f"Unknown recording columns: {sorted(unknown)}")
        read_columns = list(dict.fromkeys((*columns, *(name for filters in filter_sets for name, _ in filters))))
    if not filter_sets:
        return
    filter_indices = tuple(
        tuple((schema.get_field_index(name), value) for name, value in filters)
        for filters in filter_sets
    )
    for row_group in range(view.parquet.num_row_groups):
        check_cancelled()
        metadata = view.parquet.metadata.row_group(row_group)
        candidates = []
        for filters, indices in zip(filter_sets, filter_indices, strict=True):
            excluded = False
            for column_index, value in indices:
                statistics = metadata.column(column_index).statistics
                if statistics is None:
                    continue
                if value is None:
                    excluded = statistics.null_count == 0
                else:
                    excluded = (
                        statistics.null_count == metadata.num_rows
                        or (statistics.has_min_max and not statistics.min <= value <= statistics.max)
                    )
                if excluded:
                    break
            if not excluded:
                candidates.append(filters)
        if not candidates:
            continue
        for batch in view.parquet.iter_batches(
            batch_size=batch_size, columns=read_columns, row_groups=[row_group]
        ):
            check_cancelled()
            selected = None
            for filters in candidates:
                matched = None
                for name, value in filters:
                    column = batch.column(name)
                    field_match = pc.is_null(column) if value is None else pc.fill_null(pc.equal(column, value), False)
                    matched = field_match if matched is None else pc.and_(matched, field_match)
                selected = matched if selected is None else pc.or_(selected, matched)
            result = batch.filter(selected)
            if result.num_rows:
                yield result
