from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The only formats we offer. The addon's export_3d_model() also has a 'gltf'
# branch, but its animation export is broken (see the TODO there), so it is
# deliberately not exposed.
BlenderModelFormat = Literal["fbx", "bvh"]

DEFAULT_BLENDER_MODEL_FORMATS: list[BlenderModelFormat] = ["fbx", "bvh"]


class BlenderExportConfig(BaseModel):
    """Options forwarded to the freemocap_blender_addon for 3D model export.

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
