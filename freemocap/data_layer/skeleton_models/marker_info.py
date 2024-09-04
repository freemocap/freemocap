from pydantic import BaseModel, model_validator, Field, field_validator
from typing import Dict, List, Optional, Union


class VirtualMarkerInfo(BaseModel):
    virtual_markers: Dict[str, Dict[str, List[Union[float, str]]]]

    @field_validator("virtual_markers")
    @classmethod
    def validate_virtual_marker(cls, virtual_marker: Dict[str, List[Union[float, str]]]):
        for virtual_marker_name, virtual_marker_values in virtual_marker.items():
            marker_names = virtual_marker_values.get("marker_names", [])  # TODO: make sure this .get is valid
            marker_weights = virtual_marker_values.get("marker_weights", [])

            if len(marker_names) != len(marker_weights):
                raise ValueError(
                    f"The number of marker names must match the number of marker weights for {virtual_marker_name}. Currently there are {len(marker_names)} names and {len(marker_weights)} weights."
                )

            if not isinstance(marker_names, list) or not all(isinstance(name, str) for name in marker_names):
                raise ValueError(f"Marker names must be a list of strings for {marker_names}.")

            if not isinstance(marker_weights, list) or not all(
                isinstance(weight, (int, float)) for weight in marker_weights
            ):
                raise ValueError(f"Marker weights must be a list of numbers for {virtual_marker_name}.")

            weight_sum = sum(marker_weights)
            if not 0.99 <= weight_sum <= 1.01:  # Allowing a tiny bit of floating-point leniency
                raise ValueError(
                    f"Marker weights must sum to approximately 1 for {virtual_marker_name} Current sum is {weight_sum}."
                )

        return virtual_marker


class MarkerInfo(BaseModel):
    original_marker_names: List[str]
    virtual_marker_definition: Optional[VirtualMarkerInfo] = None
    all_markers_list: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    def copy_markers_to_all(cls, values):
        """Copy markers to all_markers_list at initialization."""
        original_marker_names = values.get("original_marker_names")
        if original_marker_names:
            # Directly initializing all_markers_list with a copy of original_marker_names
            values["all_markers_list"] = original_marker_names.copy()
        return values

    def add_virtual_markers(self, virtual_markers_dict: Dict[str, Dict[str, List[Union[float, str]]]]):
        """Add virtual markers and update all_markers_list."""
        self.virtual_marker_definition = VirtualMarkerInfo(virtual_markers=virtual_markers_dict)
        for virtual_marker_name in self.virtual_marker_definition.virtual_markers.keys():
            if virtual_marker_name not in self.all_markers_list:
                self.all_markers_list.append(virtual_marker_name)

    @property
    def all_markers(self) -> List[str]:
        """Publicly expose the combined list of markers."""
        return self.all_markers_list

    @classmethod
    def create(cls, marker_list: List[str]):
        """Class method to create an instance with initial marker names."""
        return cls(original_marker_names=marker_list)
