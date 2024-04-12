from pydantic import BaseModel, root_validator, Field, validator
from typing import Dict, List, Optional, Union


class VirtualMarkerInfo(BaseModel):
    virtual_markers: Dict[str, Dict[str, List[Union[str, int, float]]]]

    @validator("virtual_markers", each_item=True)
    def validate_virtual_marker(cls, virtual_marker: Dict[str, List[Union[str, int, float]]]):
        marker_names = virtual_marker.get("marker_names", [])
        marker_weights = virtual_marker.get("marker_weights", [])

        if len(marker_names) != len(marker_weights):
            raise ValueError(
                f"The number of marker names must match the number of marker weights for {virtual_marker}. Currently there are {len(marker_names)} names and {len(marker_weights)} weights."
            )

        if not isinstance(marker_names, list) or not all(isinstance(name, str) for name in marker_names):
            raise ValueError(f"Marker names must be a list of strings for {marker_names}.")

        if not isinstance(marker_weights, list) or not all(
            isinstance(weight, (int, float)) for weight in marker_weights
        ):
            raise ValueError(f"Marker weights must be a list of numbers for {virtual_marker}.")

        weight_sum = sum(marker_weights)
        if not 0.99 <= weight_sum <= 1.01:  # Allowing a tiny bit of floating-point leniency
            raise ValueError(
                f"Marker weights must sum to approximately 1 for {virtual_marker} Current sum is {weight_sum}."
            )

        return virtual_marker


class MarkerInfo(BaseModel):
    original_marker_names: List[str]
    virtual_marker_definition: Optional[VirtualMarkerInfo] = None
    _all_markers: List[str] = Field(default_factory=list)

    @root_validator
    def copy_markers_to_all(cls, values):
        """Copy markers to _all_markers at initialization."""
        original_marker_names = values.get("original_marker_names")
        if original_marker_names:
            # Directly initializing _all_markers with a copy of original_marker_names
            values["_all_markers"] = original_marker_names.copy()
        return values

    def add_virtual_markers(self, virtual_markers_dict: Dict[str, Dict[str, List[Union[str, int, float]]]]):
        """Add virtual markers and update _all_markers."""
        self.virtual_marker_definition = VirtualMarkerInfo(virtual_markers=virtual_markers_dict)
        for virtual_marker_name in self.virtual_marker_definition.virtual_markers.keys():
            if virtual_marker_name not in self._all_markers:
                self._all_markers.append(virtual_marker_name)

    @property
    def all_markers(self) -> List[str]:
        """Publicly expose the combined list of markers."""
        return self._all_markers

    @classmethod
    def create(cls, marker_list: List[str]):
        """Class method to create an instance with initial marker names."""
        return cls(original_marker_names=marker_list)
