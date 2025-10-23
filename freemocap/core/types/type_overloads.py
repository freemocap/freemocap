import multiprocessing

from numpydantic import NDArray, Shape
PipelineIdString = str
from pydantic import BaseModel

TrackedPoint3d = NDArray[Shape["3 xyz"], float]
TopicPublicationQueue = multiprocessing.Queue
TopicSubscriptionQueue = multiprocessing.Queue

TrackerTypeString = str #TODO - move this to `skellytracker.types` or something

FrameNumberInt = int


class Point3d(BaseModel):
    x: float
    y: float
    z: float
