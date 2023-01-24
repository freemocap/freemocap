import numpy as np
from pydantic import BaseModel


class TweakedModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True


class Data3dMultiFramePayload(TweakedModel):
    has_data: bool = (True,)
    data3d_trackedPointNum_xyz: np.ndarray = None
    data3d_trackedPointNum_reprojectionError: np.ndarray = None
