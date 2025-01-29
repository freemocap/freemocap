from numpydantic import NDArray, Shape
from pydantic import BaseModel


class Positional6DOF(BaseModel):
    translation: NDArray[Shape["3 xyz"], float]
    rotation: NDArray[Shape["3 xyz"], float]
