from pyqtgraph.parametertree import Parameter

from freemocap.core_processes.process_motion_capture_videos.session_processing_parameter_models import (
    MediapipeParametersModel,
)


def create_mediapipe_parameter_group(
    parameter_model: MediapipeParametersModel = MediapipeParametersModel(),
) -> Parameter:
    model_complexity_list = [
        "0 (Fastest/Least accurate)",
        "1 (Middle ground)",
        "2 (Slowest/Most accurate)",
    ]
    return Parameter.create(
        name="Mediapipe",
        type="group",
        children=[
            dict(
                name="Model Complexity",
                type="list",
                limits=model_complexity_list,
                value=model_complexity_list[parameter_model.model_complexity],
                tip="Which Mediapipe model to use - higher complexity is slower but more accurate. "
                "Variable name in `mediapipe` code: `model_complexity`",
            ),
            dict(
                name="Minimum Detection Confidence",
                type="float",
                value=parameter_model.min_detection_confidence,
                step=0.05,
                limits=(0.0, 1.0),
                tip="Minimum confidence for a skeleton detection to be considered valid. "
                "Variable name in `mediapipe` code: `min_detection_confidence`."
                "NOTE - Never trust a machine learning model's estimates of their own confidence!",
            ),
            dict(
                name="Minimum Tracking Confidence",
                type="float",
                value=parameter_model.min_tracking_confidence,
                step=0.05,
                limits=(0.0, 1.0),
                tip="Minimum confidence needed to use the previous frame's skeleton estiamte to predict the next one"
                "Variable name in `mediapipe` code: `min_tracking_confidence`.",
            ),
            dict(
                name="Static Image Mode",
                type="bool",
                value=parameter_model.static_image_mode,
                tip="If true, the model will process each image independently, without tracking across frames."
                "I think this is equivalent to setting `min_tracking_confidence` to 0.0"
                "Variable name in `mediapipe` code: `static_image_mode`",
            ),
        ],
    )
