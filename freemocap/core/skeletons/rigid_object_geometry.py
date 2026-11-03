"""Serializable cross-component provenance for a Forge-prepared object frame."""
from pydantic import BaseModel, ConfigDict, Field
from skellyforge.core.skeleton.stl_rigid_body import StlRigidBodyDefinition


class RigidObjectGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    feature_names: tuple[str, ...]
    segment_name: str
    source_mesh_units: str
    mesh_sha256: str | None
    reference_unit_mm: float = Field(gt=0)
    # Row-major affine matrices multiply homogeneous column coordinates.
    # Input units are object mm / original mesh units; output is segment reference units.
    object_to_segment_reference: tuple[float, ...] = Field(min_length=16, max_length=16)
    source_mesh_to_segment_reference: tuple[float, ...] = Field(min_length=16, max_length=16)
    segment_reference_to_source_mesh: tuple[float, ...] = Field(min_length=16, max_length=16)

    @classmethod
    def from_definition(cls, definition: StlRigidBodyDefinition) -> "RigidObjectGeometry":
        return cls(feature_names=definition.feature_names, segment_name=definition.segment_name,
                   source_mesh_units=definition.source_mesh_units, mesh_sha256=definition.mesh_sha256,
                   reference_unit_mm=definition.reference_unit_mm,
                   object_to_segment_reference=tuple(definition.object_to_segment_reference.ravel()),
                   source_mesh_to_segment_reference=tuple(definition.source_mesh_to_segment_reference.ravel()),
                   segment_reference_to_source_mesh=tuple(definition.segment_reference_to_source_mesh.ravel()))
