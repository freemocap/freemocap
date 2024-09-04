import logging
import multiprocessing
from typing import Dict, Union
import numpy as np


from freemocap.core_processes.post_process_skeleton_data.calculate_center_of_mass import (
    calculate_center_of_mass_from_skeleton,
)
from freemocap.core_processes.post_process_skeleton_data.create_skeleton import create_skeleton_model
from freemocap.core_processes.post_process_skeleton_data.enforce_rigid_bones import enforce_rigid_bones_from_skeleton
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.logging.configure_logging import log_view_logging_format_string

logger = logging.getLogger(__name__)


def calculate_anatomical_data(
    processing_parameters: ProcessingParameterModel,
    skel3d_frame_marker_xyz: np.ndarray,
    queue: multiprocessing.Queue,
) -> Dict[str, Union[np.ndarray, None]]:
    if queue:
        handler = DirectQueueHandler(queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)

    logger.info("Creating skeleton model...")
    skeleton = create_skeleton_model(
        actual_markers=processing_parameters.tracking_model_info.landmark_names,
        segment_connections=processing_parameters.tracking_model_info.segment_connections,
        virtual_markers=processing_parameters.tracking_model_info.virtual_markers_definitions,
        joint_hierarchy=processing_parameters.tracking_model_info.joint_hierarchy,
        center_of_mass_info=processing_parameters.tracking_model_info.center_of_mass_definitions,
        num_tracked_points=processing_parameters.tracking_model_info.num_tracked_points,
    )

    skeleton.integrate_freemocap_3d_data(skel3d_frame_marker_xyz)

    logger.info("Calculating center of mass...")
    try:
        segment_COM_frame_imgPoint_XYZ, totalBodyCOM_frame_XYZ = calculate_center_of_mass_from_skeleton(
            skeleton=skeleton
        )
    except ValueError:
        logger.warning("Center of mass cannot be calculated for this tracking model")
        segment_COM_frame_imgPoint_XYZ = totalBodyCOM_frame_XYZ = None
    except AttributeError as e:
        raise e

    logger.info("Enforcing rigid bones...")
    rigid_bones_data = enforce_rigid_bones_from_skeleton(skeleton=skeleton)

    return {
        "segment_COM": segment_COM_frame_imgPoint_XYZ,
        "total_body_COM": totalBodyCOM_frame_XYZ,
        "rigid_bones_data": rigid_bones_data,
    }
