import multiprocessing

import msgspec

PointIndex = int
PipelineIdString = str
TrackedPointNameString = str
VideoIdString = str

TopicPublicationQueue = multiprocessing.Queue
TopicSubscriptionQueue = multiprocessing.Queue

TrackerTypeString = str  # TODO - move this to `skellytracker.types` or something

FrameNumberInt = int


class Point3d(msgspec.Struct):
    x: float
    y: float
    z: float
