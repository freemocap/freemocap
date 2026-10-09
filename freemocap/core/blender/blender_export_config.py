"""Core-owned export options, translated to the installed add-on contract."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class BlenderExportConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    formats: list[Literal["fbx", "bvh"]] = Field(default_factory=list)
    rest_pose: Literal["tpose", "apose"] = Field(default="tpose", alias="restPose")
    apply_foot_locking: bool = Field(default=False, alias="applyFootLocking")
    limit_hand_markers_range_of_motion: bool = Field(default=False, alias="limitHandMarkersRangeOfMotion")

    def addon_payload(self, route: str) -> dict:
        if route == "parquet_segments" and (self.rest_pose != "tpose" or self.apply_foot_locking or self.limit_hand_markers_range_of_motion):
            raise ValueError("Saved segment poses do not support rest-pose changes or animation cleanup; select Parquet constraints")
        return dict(export_3d_model=dict(formats=self.formats),
                    add_rig=dict(rest_pose=self.rest_pose),
                    motion_cleanup=dict(apply_foot_locking=self.apply_foot_locking,
                        limit_hand_markers_range_of_motion=self.limit_hand_markers_range_of_motion))
