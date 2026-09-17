from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The only formats we offer. The addon's export_3d_model() also has a 'gltf'
# branch, but its animation export is broken (see the TODO there), so it is
# deliberately not exposed.
BlenderModelFormat = Literal["fbx", "bvh"]

# Rest pose the addon builds the armature in.
ArmatureRestPose = Literal["tpose", "apose"]

DEFAULT_BLENDER_MODEL_FORMATS: list[BlenderModelFormat] = ["fbx", "bvh"]
DEFAULT_ARMATURE_REST_POSE: ArmatureRestPose = "tpose"


class BlenderExportConfig(BaseModel):
    """Options forwarded to the freemocap_blender_addon for the Blender export.

    These travel to Blender as a serialized argument on the subprocess command
    line, so they must stay JSON-serializable. The addon ignores options it does
    not recognize, which lets this model grow ahead of the addon release it is
    paired with.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    formats: list[BlenderModelFormat] = Field(
        default_factory=lambda: list(DEFAULT_BLENDER_MODEL_FORMATS),
        description=(
            "3D model formats to write during the Blender export. Each format produces "
            "a sibling file (e.g. '<recording>.fbx' and '<recording>.bvh') in the "
            "'3d_models' subfolder of the recording. May be empty, in which case the "
            "3D model export stage is skipped entirely."
        ),
    )
    rest_pose: ArmatureRestPose = Field(
        default=DEFAULT_ARMATURE_REST_POSE,
        alias="restPose",
        description=(
            "Rest pose the armature is built in: 'tpose' or 'apose'. Affects the rig "
            "created in the .blend file and anything exported from it."
        ),
    )
    apply_foot_locking: bool = Field(
        default=False,
        alias="applyFootLocking",
        description=(
            "If True, run the addon's foot-locking cleanup over the marker motion before "
            "the scene is set up. Off by default because it rewrites the marker positions."
        ),
    )
