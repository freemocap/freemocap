from typing import Dict, List, Optional
from pydantic import BaseModel, root_validator
import numpy as np

from freemocap.data_layer.skeleton_models.anthropometric_data import CenterOfMassDefinitions, SegmentAnthropometry
from freemocap.data_layer.skeleton_models.joint_hierarchy import JointHierarchy
from freemocap.data_layer.skeleton_models.marker_info import MarkerInfo
from freemocap.data_layer.skeleton_models.segments import Segment, Segments


class Skeleton(BaseModel):
    markers: MarkerInfo
    segments: Optional[Dict[str, Segment]] = None
    marker_data: Dict[str, np.ndarray] = {}
    virtual_marker_data: Dict[str, np.ndarray] = {}
    joint_hierarchy: Optional[Dict[str, List[str]]] = None
    center_of_mass_definitions: Optional[Dict[str, SegmentAnthropometry]] = None

    class Config:
        arbitrary_types_allowed = True

    def add_segments(self, segment_connections: Dict[str, Segment]):
        """
        Adds segment connection data to the skeleton model.

        Parameters:
        - segment_connections: A dictionary where each key is a segment name and its value is a dictionary
          with information about that segment (e.g., 'proximal', 'distal' marker names).
        """
        segments_model = Segments(
            markers=self.markers,
            segment_connections={name: segment for name, segment in segment_connections.items()},
        )
        self.segments = segments_model.segment_connections

    def add_joint_hierarchy(self, joint_hierarchy: Dict[str, List[str]]):
        """
        Adds joint hierarchy data to the skeleton model.

        Parameters:
        - joint_hierarchy: A dictionary with joint names as keys and lists of connected marker names as values.
        """
        # TODO: We only use this pydantic model for validation - we could easily put that validator here and skip a layer of indirection
        joint_hierarchy_model = JointHierarchy(markers=self.markers, joint_hierarchy=joint_hierarchy)
        self.joint_hierarchy = joint_hierarchy_model.joint_hierarchy

    def add_center_of_mass_definitions(self, center_of_mass_definitions: Dict[str, SegmentAnthropometry]):
        """
        Adds anthropometric data to the skeleton model.

        Parameters:
        - anthropometric_data: A dictionary containing segment mass percentages.
        """
        # TODO: Similar to above, pydantic model is just doing validaiton we can do here (model doesn't need to persist over time)
        anthropometrics = CenterOfMassDefinitions(center_of_mass_definitions=center_of_mass_definitions)
        self.center_of_mass_definitions = anthropometrics.center_of_mass_definitions

    def integrate_freemocap_3d_data(self, freemocap_3d_data: np.ndarray):
        self.num_frames = freemocap_3d_data.shape[
            0
        ]  # TODO: This maybe should be defined in the model and only filled in here
        num_markers_in_data = freemocap_3d_data.shape[1]
        original_marker_names_list = self.markers.original_marker_names
        num_markers_in_model = len(original_marker_names_list)

        if num_markers_in_data != num_markers_in_model:
            raise ValueError(
                f"The number of markers in the 3D data ({num_markers_in_data}) does not match "
                f"the number of markers in the model ({num_markers_in_model})."
            )

        for i, marker_name in enumerate(original_marker_names_list):
            self.marker_data[marker_name] = freemocap_3d_data[:, i, :]

    def calculate_virtual_markers(self):
        if not self.marker_data:
            raise ValueError(
                "3d marker data must be integrated before calculating virtual markers. Run `integrate_freemocap_3d_data()` first."
            )

        if not self.markers.virtual_marker_definition:
            raise ValueError(
                "Virtual marker info must be defined before calculating virtual markers. Run `add_virtual_markers()` first."
            )

        for vm_name, vm_info in self.markers.virtual_marker_definition.virtual_markers.items():
            vm_positions = np.zeros((self.marker_data[next(iter(self.marker_data))].shape[0], 3))
            for marker_name, weight in zip(vm_info["marker_names"], vm_info["marker_weights"]):
                vm_positions += self.marker_data[marker_name] * weight
            self.virtual_marker_data[vm_name] = vm_positions

        self.marker_data.update(self.virtual_marker_data)

    def get_segment_markers(self, segment_name: str) -> Dict[str, np.ndarray]:
        """Returns a dictionary with the positions of the proximal and distal markers for a segment."""
        if not self.segments:
            raise ValueError("Segments must be defined before getting segment markers.")

        if not self.trajectories:
            raise ValueError("Trajectories must be defined before getting segment markers.")

        segment = self.segments.get(segment_name)
        if not segment:
            raise ValueError(f"Segment '{segment_name}' is not defined in the skeleton.")

        proximal_trajectories = self.trajectories.get(segment.proximal)
        distal_trajectories = self.trajectories.get(segment.distal)

        return {"proximal": proximal_trajectories, "distal": distal_trajectories}

    @property
    def trajectories(self) -> Dict[str, np.ndarray]:
        return self.marker_data
