from pyqtgraph.parametertree import Parameter, ParameterTree

from freemocap.core_processes.post_process_skeleton_data.parameter_info_models.recording_processing_parameter_models import MediapipeParametersModel, \
    RecordingProcessingParameterModel, AniposeTriangulate3DParametersModel, PostProcessingParametersModel, \
    ButterworthFilterParametersModel

BUTTERWORTH_ORDER = "Order"

BUTTERWORTH_CUTOFF_FREQUENCY = "Cutoff Frequency"

POST_PROCESSING_FRAME_RATE = "framerate"

BUTTERWORTH_FILTER_TREE_NAME = "Butterworth Filter"

USE_RANSAC_METHOD = "Use RANSAC Method"

ANIPOSE_CONFIDENCE_CUTOFF = "Confidence Threshold Cut-off"

ANIPOSE_TREE_NAME = "Anipose Triangulation"

STATIC_IMAGE_MODE = "Static Image Mode"

MINIUMUM_TRACKING_CONFIDENCE = "Minimum Tracking Confidence"

MINIMUM_DETECTION_CONFIDENCE = "Minimum Detection Confidence"

MODEL_COMPLEXITY = "Model Complexity"

MEDIAPIPE_TREE_NAME = "Mediapipe"


def create_mediapipe_parameter_group(
        parameter_model: MediapipeParametersModel = MediapipeParametersModel(),
) -> Parameter:
    model_complexity_list = [
        "0 (Fastest/Least accurate)",
        "1 (Middle ground)",
        "2 (Slowest/Most accurate)",
    ]
    return Parameter.create(
        name=MEDIAPIPE_TREE_NAME,
        type="group",
        children=[
            dict(
                name=MODEL_COMPLEXITY,
                type="list",
                limits=model_complexity_list,
                value=model_complexity_list[parameter_model.model_complexity],
                tip="Which Mediapipe model to use - higher complexity is slower but more accurate. "
                    "Variable name in `mediapipe` code: `model_complexity`",
            ),
            dict(
                name=MINIMUM_DETECTION_CONFIDENCE,
                type="float",
                value=parameter_model.min_detection_confidence,
                step=0.05,
                limits=(0.0, 1.0),
                tip="Minimum confidence for a skeleton detection to be considered valid. "
                    "Variable name in `mediapipe` code: `min_detection_confidence`."
                    "NOTE - Never trust a machine learning model's estimates of their own confidence!",
            ),
            dict(
                name=MINIUMUM_TRACKING_CONFIDENCE,
                type="float",
                value=parameter_model.min_tracking_confidence,
                step=0.05,
                limits=(0.0, 1.0),
                tip="Minimum confidence needed to use the previous frame's skeleton estiamte to predict the next one"
                    "Variable name in `mediapipe` code: `min_tracking_confidence`.",
            ),
            dict(
                name=STATIC_IMAGE_MODE,
                type="bool",
                value=parameter_model.static_image_mode,
                tip="If true, the model will process each image independently, without tracking across frames."
                    "I think this is equivalent to setting `min_tracking_confidence` to 0.0"
                    "Variable name in `mediapipe` code: `static_image_mode`",
            ),
        ],
    )


def create_3d_triangulation_prarameter_group(
        parameter_model: AniposeTriangulate3DParametersModel = AniposeTriangulate3DParametersModel(),
) -> Parameter:
    return Parameter.create(
        name=ANIPOSE_TREE_NAME,
        type="group",
        children=[
            dict(
                name=ANIPOSE_CONFIDENCE_CUTOFF,
                type="float",
                value=parameter_model.confidence_threshold_cutoff,
                tip="Confidence threshold cut-off for triangulation. "
                    "NOTE - Never trust a machine learning model's estimates of their own confidence! "
                    "TODO - Something similar that uses `reprojection_error` instead of `confidence`",
            ),
            dict(
                name=USE_RANSAC_METHOD,
                type="bool",
                value=parameter_model.use_triangulate_ransac_method,
                tip="If true, use `anipose`'s `triangulate_ransac` method instead of the default `triangulate_simple` method. "
                    "NOTE - Much slower than the 'simple' method, but might be more accurate and better at rejecting bad camera views. Needs more testing and evaluation to see if it's worth it. ",
            ),
        ],
    )


def create_post_processing_parameter_group(
        parameter_model: PostProcessingParametersModel = PostProcessingParametersModel(),
) -> Parameter:
    return Parameter.create(
        name=BUTTERWORTH_FILTER_TREE_NAME,
        type="group",
        children=[
            dict(
                name=POST_PROCESSING_FRAME_RATE,
                type="float",
                value=parameter_model.butterworth_filter_parameters.sampling_rate,
                tip="Framerate of the recording " "TODO - Calculate this from the recorded timestamps....",
            ),
            dict(
                name=BUTTERWORTH_CUTOFF_FREQUENCY,
                type="float",
                value=parameter_model.butterworth_filter_parameters.cutoff_frequency,
                tip="Oscillations above this frequency will be filtered from the data. ",
            ),
            dict(
                name=BUTTERWORTH_ORDER,
                type="int",
                value=parameter_model.butterworth_filter_parameters.order,
                tip="Order of the filter."
                    "NOTE - I'm not really sure what this parameter does, but this is what I see in other people's Methods sections so....   lol",
            ),
        ],
        tip="Low-pass, zero-lag, Butterworth filter to remove high frequency oscillations/noise from the data. ",
    )


def extract_mediapipe_parameter_model_from_parameter_tree(
        parameter_tree: ParameterTree,
) -> RecordingProcessingParameterModel:
    return RecordingProcessingParameterModel(
        mediapipe_parameters_model=MediapipeParametersModel(
            model_complexity=parameter_tree.param(MEDIAPIPE_TREE_NAME).param(MODEL_COMPLEXITY).value(),
            min_detection_confidence=parameter_tree.param(MEDIAPIPE_TREE_NAME).param(
                MINIMUM_DETECTION_CONFIDENCE).value(),
            min_tracking_confidence=parameter_tree.param(MEDIAPIPE_TREE_NAME).param(
                MINIUMUM_TRACKING_CONFIDENCE).value(),
            static_image_mode=parameter_tree.param(MEDIAPIPE_TREE_NAME).param(STATIC_IMAGE_MODE).value(), ),

        anipose_triangulate_3d_parameters_model=AniposeTriangulate3DParametersModel(
            confidence_threshold_cutoff=parameter_tree.param(ANIPOSE_TREE_NAME).param(
                ANIPOSE_CONFIDENCE_CUTOFF).value(),
            use_triangulate_ransac_method=parameter_tree.param(ANIPOSE_TREE_NAME).param(USE_RANSAC_METHOD).value(),
            ),
        post_processing_parameters_model=PostProcessingParametersModel(
            framerate=parameter_tree.param(BUTTERWORTH_FILTER_TREE_NAME).param(POST_PROCESSING_FRAME_RATE).value(),
            butterworth_filter_parameters=ButterworthFilterParametersModel(
                sampling_rate=parameter_tree.param(BUTTERWORTH_FILTER_TREE_NAME).param(
                    POST_PROCESSING_FRAME_RATE).value(),
                cutoff_frequency=parameter_tree.param(BUTTERWORTH_FILTER_TREE_NAME).param(
                    BUTTERWORTH_CUTOFF_FREQUENCY).value(),
                order=parameter_tree.param(BUTTERWORTH_FILTER_TREE_NAME).param(BUTTERWORTH_ORDER).value(),
                ),
            )
        ) #thanks github co-pilot lol
