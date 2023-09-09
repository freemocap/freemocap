from freemocap_web.core.mocap import Mocap
from freemocap_web.core.project import Project


def mocap(video: str):
    return Mocap.from_project(
        project=Project.from_video(video=video))
