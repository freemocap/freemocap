import logging

# using relative imports so it can run in blender subprocess, hopefully?

from core_functions.main_controller import MainController
from data_models.parameter_models.load_parameters_config import load_default_parameters_config
from data_models.parameter_models.parameter_models import Config

logger = logging.getLogger(__name__)


def ajc_addon_main(recording_path: str,
         config: Config = load_default_parameters_config()):
    controller = MainController(recording_path=recording_path,
                                config=config)

    controller.run_all()

    logger.success("Done!!!")


if __name__ == "__main__" or __name__ == "<run_path>":
    try:
        import bpy
        from pathlib import Path

        fmc_adapter_tool = bpy.context.scene.fmc_adapter_properties
        recording_path = fmc_adapter_tool.recording_path

        if not Path(recording_path).exists():
            raise ValueError(f"Recording path {recording_path} does not exist!")
    except Exception as e:
        logging.warning(f"Could not load recording path from Blender. Using default path instead. Error: {e}")

        from ajc_freemocap_blender_addon.core_functions.setup_scene.get_path_to_sample_data import get_path_to_sample_data

        recording_path = get_path_to_sample_data()

    logging.info(f"Running {__file__} with recording_path={recording_path}")
    main(recording_path=recording_path)
