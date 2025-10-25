import multiprocessing

from numpydantic import NDArray, Shape
from pydantic import BaseModel
PointIndex = int
PipelineIdString = str

TopicPublicationQueue = multiprocessing.Queue
TopicSubscriptionQueue = multiprocessing.Queue

TrackerTypeString = str #TODO - move this to `skellytracker.types` or something

FrameNumberInt = int


class Point3d(BaseModel):
    x: float
    y: float
    z: float
