from ctypes import Union

import numpy as np
from pydantic import BaseModel


class TweakedModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True


class Data3dFullSessionPayload(TweakedModel):
    has_data: bool = True,
    data3d_numFrames_numTrackedPoints_XYZ: np.ndarray = None
    data3d_numFrames_numTrackedPoint_reprojectionError: np.ndarray = None

    def threshold_by_reprojection_error(self, threshold:Union[int,float]):
        """return data that is below a given threshold value (TODO- figure out how to do this, lol)"""
        pass
