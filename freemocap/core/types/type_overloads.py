import multiprocessing
import multiprocessing.queues

import msgspec

PointIndex = int
PipelineIdString = str
TrackedPointNameString = str
VideoIdString = str

TopicPublicationQueue = multiprocessing.queues.Queue
TopicSubscriptionQueue = multiprocessing.queues.Queue

TrackerTypeString = str  # TODO - move this to `skellytracker.types` or something

FrameNumberInt = int


class Point3d(msgspec.Struct):
    x: float
    y: float
    z: float
