from typing import Dict, List
from pydantic import BaseModel, root_validator

from freemocap.data_layer.skeleton_models.marker_info import MarkerInfo


class JointHierarchy(BaseModel):
    markers: MarkerInfo
    joint_hierarchy: Dict[str, List[str]]

    @root_validator
    def check_that_all_markers_exist(cls, values):
        marker_names = values.get("markers").all_markers
        joint_hierarchy = values.get("joint_hierarchy")

        for joint_name, joint_connections in joint_hierarchy.items():
            if joint_name not in marker_names:
                raise ValueError(f"The joint {joint_name} is not in the list of markers or virtual markers.")
            for connected_marker in joint_connections:
                if connected_marker not in marker_names:
                    raise ValueError(
                        f"The connected marker {connected_marker} for {joint_name} is not in the list of markers or virtual markers."
                    )

        return values
