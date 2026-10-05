"""Versioned stage provenance inside the existing run.processing extension point.

Absence means unknown historical provenance, never today's default configuration.
The outer recording schema stays at 1 so installed Forge recording readers remain
compatible. New readers validate this reserved extension; older readers ignore it.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage

PROVENANCE_KEY = "stage_provenance"


class StageProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    attempt_id: str = Field(min_length=1)
    recorded_at: datetime
    effective_settings: dict[str, JsonValue]
    default_settings: dict[str, JsonValue] | None
    input_signatures: dict[str, str]
    software: dict[str, JsonValue]
    output_sources: tuple[str, ...]
    limitations: tuple[str, ...] = ()
    base_run_id: int | None = Field(default=None, ge=0)
    base_descriptor_signature: str | None = None

    @model_validator(mode="after")
    def validate_identity(self):
        if self.recorded_at.utcoffset() is None:
            raise ValueError("Provenance time must include a timezone")
        if not self.input_signatures or any(not value for value in self.input_signatures.values()):
            raise ValueError("Provenance requires named input signatures")
        if not self.output_sources or len(set(self.output_sources)) != len(self.output_sources):
            raise ValueError("Provenance requires unique output sources")
        if not self.software:
            raise ValueError("Provenance requires software identity")
        if (self.base_run_id is None) != (self.base_descriptor_signature is None):
            raise ValueError("Base run and descriptor signature must be supplied together")
        return self


class StageProvenanceSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    stages: dict[ProcessingStage, StageProvenance] = Field(default_factory=dict)


def stage_provenance(processing: dict, group: str) -> StageProvenanceSet:
    """Return validated recorded entries; an empty set makes no historical claims."""
    value = processing.get(group, {}).get(PROVENANCE_KEY)
    return StageProvenanceSet() if value is None else StageProvenanceSet.model_validate(value)


def set_stage_provenance(processing: dict, group: str, entries: dict[ProcessingStage, StageProvenance]) -> dict:
    """Copy the group envelope; preserve all unrelated processing reports."""
    result = dict(processing)
    settings = dict(result.get(group, {}))
    if entries:
        settings[PROVENANCE_KEY] = StageProvenanceSet(stages=entries).model_dump(mode="json")
    else:
        settings.pop(PROVENANCE_KEY, None)
    result[group] = settings
    return result
