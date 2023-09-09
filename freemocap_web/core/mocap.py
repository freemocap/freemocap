from dataclasses import dataclass

from freemocap_web.core.project import Project
from freemocap_web.core.mediapipe import MediapipeImageData


@dataclass
class Mocap:
    Project: Project
    MediapipeImageData: MediapipeImageData

    @staticmethod
    def from_project(project: Project):
        return Mocap(
            MediapipeImageData=MediapipeImageData.from_project(project),
            Project=project)

    def to_blender(self):
        from freemocap_web.core.blender import _export_active_recording_to_blender

        return _export_active_recording_to_blender(self)
