from ctypes import Union
from typing import get_origin, get_args

from pydantic import BaseModel


def create_nested_dict(pydantic_model):
    if not issubclass(pydantic_model, BaseModel):
        return str(pydantic_model)

    model_dict = {}
    for name, field in pydantic_model.__annotations__.items():
        origin = get_origin(field)
        if origin is Union:
            args = get_args(field)
            if type(None) in args:
                # Remove 'None' type from Union type
                args = tuple(arg for arg in args if arg is not type(None))  # noqa: E721
            if len(args) == 1:
                field = args[0]
                origin = get_origin(field)
        if origin is dict or origin is list:
            model_dict[name] = str(field)
        else:
            model_dict[name] = create_nested_dict(field)
    return model_dict


if __name__ == "__main__":
    from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import (
        mediapipe_skeleton_schema,
    )
    from freemocap.data_layer.data_saver import SkeletonSchema

    skeleton_schema = SkeletonSchema(schema_dict=mediapipe_skeleton_schema)
    print(create_nested_dict(skeleton_schema))
