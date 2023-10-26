import logging
from pathlib import Path

from ajc_freemocap_blender_addon.blender_interface.utilities.get_or_create_freemocap_data_handler import \
    get_or_create_freemocap_data_handler
from ajc_freemocap_blender_addon.core_functions.bones.enforce_rigid_bones import enforce_rigid_bones
from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.operations.freemocap_empties_from_parent_object import \
    freemocap_empties_from_parent_object
from ajc_freemocap_blender_addon.core_functions.mesh.attach_mesh_to_rig import attach_mesh_to_rig
from ajc_freemocap_blender_addon.core_functions.empties.creation.create_freemocap_empties import create_freemocap_empties
from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.helpers.saver import \
    FreemocapDataSaver
from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.operations.fix_hand_data import \
    fix_hand_data
from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.operations.put_skeleton_on_ground import \
    put_skeleton_on_ground
from ajc_freemocap_blender_addon.core_functions.load_data.load_freemocap_data import load_freemocap_data
from ajc_freemocap_blender_addon.core_functions.load_data.load_videos import load_videos
from ajc_freemocap_blender_addon.core_functions.rig.add_rig import add_rig
from ajc_freemocap_blender_addon.core_functions.setup_scene.make_parent_empties import create_freemocap_parent_empty
from ajc_freemocap_blender_addon.core_functions.setup_scene.set_start_end_frame import set_start_end_frame
from ajc_freemocap_blender_addon.data_models.parameter_models.parameter_models import Config

logger = logging.getLogger(__name__)


class MainController:
    """
    This class is used to run the program as a main script.
    """

    def __init__(self,
                 recording_path: str,
                 config: Config):
        self.config = config

        self.recording_path = recording_path
        self.recording_name = Path(self.recording_path).stem
        self.origin_name = f"{self.recording_name}_origin"
        self.rig_name = "rig"
        self._create_parent_empties()
        self.freemocap_data_handler = get_or_create_freemocap_data_handler(recording_path=self.recording_path)
        self.empties = None

    def _create_parent_empties(self):
        self.data_parent_object = create_freemocap_parent_empty(name=self.origin_name)
        self._empty_parent_object = create_freemocap_parent_empty(name=f"empties",
                                                                  parent_object=self.data_parent_object)
        self._video_parent_object = create_freemocap_parent_empty(name=f"videos",
                                                                  parent_object=self.data_parent_object)

    def load_freemocap_data(self):
        try:
            logger.info("Loading freemocap data....")
            self.freemocap_data_handler = load_freemocap_data(recording_path=self.recording_path)
            self.freemocap_data_handler.mark_processing_stage("original_from_file")
            set_start_end_frame(number_of_frames=self.freemocap_data_handler.number_of_frames)
        except Exception as e:
            logger.error(f"Failed to load freemocap data: {e}")
            raise e

    def calculate_virtual_trajectories(self):
        try:
            logger.info("Calculating virtual trajectories....")
            self.freemocap_data_handler.calculate_virtual_trajectories()
            self.freemocap_data_handler.mark_processing_stage("add_virtual_trajectories")
        except Exception as e:
            logger.error(f"Failed to calculate virtual trajectories: {e}")
            logger.exception(e)
            raise e

    def put_data_in_inertial_reference_frame(self):
        try:
            logger.info("Putting freemocap data in inertial reference frame....")
            put_skeleton_on_ground(handler=self.freemocap_data_handler)
        except Exception as e:
            logger.error(f"Failed when trying to put freemocap data in inertial reference frame: {e}")
            logger.exception(e)
            raise e

    def enforce_rigid_bones(self):
        logger.info("Enforcing rigid bones...")
        try:
            self.freemocap_data_handler = enforce_rigid_bones(handler=self.freemocap_data_handler)
        except Exception as e:
            logger.error(f"Failed during `enforce rigid bones`, error: `{e}`")
            logger.exception(e)
            raise e

    def fix_hand_data(self):
        try:
            logger.info("Fixing hand data...")
            self.freemocap_data_handler = fix_hand_data(handler=self.freemocap_data_handler)
        except Exception as e:
            logger.error(f"Failed during `fix hand data`, error: `{e}`")
            logger.exception(e)
            raise e

    def save_data_to_disk(self):
        try:
            logger.info("Saving data to disk...")
            FreemocapDataSaver(handler=self.freemocap_data_handler).save(
                recording_path=self.recording_path)
        except Exception as e:
            logger.error(f"Failed to save data to disk: {e}")
            logger.exception(e)
            raise e

    def create_empties(self):
        try:
            logger.info("Creating keyframed empties....")

            self.empties = create_freemocap_empties(handler=self.freemocap_data_handler,
                                                    parent_object=self._empty_parent_object,
                                                    )
            logger.success(f"Finished creating keyframed empties: {self.empties.keys()}")
        except Exception as e:
            logger.error(f"Failed to create keyframed empties: {e}")

    def add_rig(self):
        try:
            logger.info("Adding rig...")
            add_rig(empties=self.empties,
                    bones=self.freemocap_data_handler.metadata['bones'],
                    rig_name=self.rig_name,
                    parent_object=self.data_parent_object,
                    keep_symmetry=self.config.add_rig.keep_symmetry,
                    add_fingers_constraints=self.config.add_rig.add_fingers_constraints,
                    use_limit_rotation=self.config.add_rig.use_limit_rotation,
                    )
        except Exception as e:
            logger.error(f"Failed to add rig: {e}")
            logger.exception(e)
            raise e

    def attach_mesh_to_rig(self):
        try:
            logger.info("Adding body mesh...")
            attach_mesh_to_rig(body_mesh_mode=self.config.add_body_mesh.body_mesh_mode,
                               rig_name=self.rig_name,
                               empties = self.empties,)
        except Exception as e:
            logger.error(f"Failed to attach mesh to rig: {e}")
            logger.exception(e)
            raise e

    def add_videos(self):
        try:
            logger.info("Loading videos as planes...")
            load_videos(recording_path=self.recording_path,
                        parent_object=self._video_parent_object,)
        except Exception as e:
            logger.error(e)
            logger.exception(e)
            raise e

    def run_all(self):
        logger.info("Running all stages...")
        self.load_freemocap_data()
        self.calculate_virtual_trajectories()
        self.put_data_in_inertial_reference_frame()
        self.enforce_rigid_bones()
        self.fix_hand_data()
        self.save_data_to_disk()
        self.create_empties()
        self.add_rig()
        self.attach_mesh_to_rig()
        self.add_videos()
        self.setup_scene()
        # export_fbx(recording_path=recording_path, )

    def setup_scene(self):
        import bpy
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:  # iterate through areas in current screen
                if area.type == "VIEW_3D":
                    for space in area.spaces:  # iterate through spaces in current VIEW_3D area
                        if space.type == "VIEW_3D":  # check if space is a 3D view
                            space.shading.type = "MATERIAL"

