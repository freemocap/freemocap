import json

from ajc_freemocap_blender_addon.data_models.parameter_models.parameter_models import AdjustEmpties, ReduceBoneLengthDispersion, \
    ReduceShakiness, AddRig, AddBodyMesh, Config


# Define the data classes to represent the JSON structure


def load_default_parameters_config(filename: str = None) -> Config:
    if filename is not None:
        with open(filename, "r") as f:
            data = json.load(f)
        # Parse JSON data into the dataclass structure
        return Config(
            # recording_path=data['recording_path'],
            adjust_empties=AdjustEmpties(**data['adjust_empties']),
            reduce_bone_length_dispersion=ReduceBoneLengthDispersion(**data['reduce_bone_length_dispersion']),
            reduce_shakiness=ReduceShakiness(**data['reduce_shakiness']),
            add_rig=AddRig(**data['add_rig']),
            add_body_mesh=AddBodyMesh(**data['add_body_mesh'])
        )
    else:
        return Config()


if __name__ == "__main__":
    from pprint import pprint as print

    default_parameters_filename = "default_parameters.json"
    config = load_default_parameters_config("default_parameters.json")
    print(config.__dict__)
