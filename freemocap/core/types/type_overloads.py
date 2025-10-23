import multiprocessing

from numpydantic import NDArray, Shape
PipelineIdString = str

TrackedPoint3d = NDArray[Shape["3 xyz"], float]
TopicPublicationQueue = multiprocessing.Queue
TopicSubscriptionQueue = multiprocessing.Queue

TrackerTypeString = str #TODO - move this to `skellytracker.types` or something

FrameNumberInt = int