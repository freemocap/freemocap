from pyqtgraph.parametertree import Parameter

from freemocap.data_layer.recording_models.post_processing_parameter_models import (
    MediapipeParametersModel,
    PostProcessingParameterModel,
    AniposeTriangulate3DParametersModel,
    PostProcessingParametersModel,
    ButterworthFilterParametersModel,
)


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

MEDIAPIPE_MODEL_COMPLEXITY = "Model Complexity"

MEDIAPIPE_TREE_NAME = "Mediapipe"

SKIP_2D_IMAGE_TRACKING_NAME = "Skip 2d image tracking?"

SKIP_3D_TRIANGULATION_NAME = "Skip 3d triangulation?"

SKIP_BUTTERWORTH_FILTER_NAME = "Skip butterworth filter?"

USE_MULTIPROCESSING_PARAMETER_NAME = "Use Multiprocessing"


def create_mediapipe_parameter_group(
    parameter_model: MediapipeParametersModel = None,
) -> Parameter:
    if parameter_model is None:
        parameter_model = MediapipeParametersModel()

    mediapipe_model_complexity_list = [
        "0 (Fastest/Least accurate)",
        "1 (Middle ground)",
        "2 (Slowest/Most accurate)",
    ]
    return Parameter.create(
        name=MEDIAPIPE_TREE_NAME,
        type="group",
        children=[
            dict(
                name=MEDIAPIPE_MODEL_COMPLEXITY,
                type="list",
                limits=mediapipe_model_complexity_list,
                value=mediapipe_model_complexity_list[parameter_model.mediapipe_model_complexity],
                tip="Which Mediapipe model to use - higher complexity is slower but more accurate. "
                "Variable name in `mediapipe` code: `mediapipe_model_complexity`",
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
    parameter_model: AniposeTriangulate3DParametersModel = None,
) -> Parameter:
    if parameter_model is None:
        parameter_model = AniposeTriangulate3DParametersModel()

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
    parameter_model: PostProcessingParametersModel = None,
) -> Parameter:
    if parameter_model is None:
        parameter_model = PostProcessingParametersModel()

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


def extract_parameter_model_from_parameter_tree(
    parameter_object: Parameter,
) -> PostProcessingParameterModel:
    parameter_values_dictionary = extract_processing_parameter_model_from_tree(parameter_object=parameter_object)

    mediapipe_model_complexity_integer = get_integer_from_mediapipe_model_complexity(
        parameter_values_dictionary[MEDIAPIPE_MODEL_COMPLEXITY]
    )

    return PostProcessingParameterModel(
        mediapipe_parameters_model=MediapipeParametersModel(
            mediapipe_model_complexity=mediapipe_model_complexity_integer,
            min_detection_confidence=parameter_values_dictionary[MINIMUM_DETECTION_CONFIDENCE],
            min_tracking_confidence=parameter_values_dictionary[MINIUMUM_TRACKING_CONFIDENCE],
            static_image_mode=parameter_values_dictionary[STATIC_IMAGE_MODE],
            skip_2d_image_tracking=parameter_values_dictionary[SKIP_2D_IMAGE_TRACKING_NAME],
            use_multiprocessing=parameter_values_dictionary[USE_MULTIPROCESSING_PARAMETER_NAME],
        ),
        anipose_triangulate_3d_parameters_model=AniposeTriangulate3DParametersModel(
            confidence_threshold_cutoff=parameter_values_dictionary[ANIPOSE_CONFIDENCE_CUTOFF],
            use_triangulate_ransac_method=parameter_values_dictionary[USE_RANSAC_METHOD],
            skip_3d_triangulation=parameter_values_dictionary[SKIP_3D_TRIANGULATION_NAME],
        ),
        post_processing_parameters_model=PostProcessingParametersModel(
            framerate=parameter_values_dictionary[POST_PROCESSING_FRAME_RATE],
            butterworth_filter_parameters=ButterworthFilterParametersModel(
                sampling_rate=parameter_values_dictionary[POST_PROCESSING_FRAME_RATE],
                cutoff_frequency=parameter_values_dictionary[BUTTERWORTH_CUTOFF_FREQUENCY],
                order=parameter_values_dictionary[BUTTERWORTH_ORDER],
            ),
            skip_butterworth_filter=parameter_values_dictionary[SKIP_BUTTERWORTH_FILTER_NAME],
        ),
    )


def get_integer_from_mediapipe_model_complexity(mediapipe_model_complexity_value: str):
    mediapipe_model_complexity_dictionary = {
        "0 (Fastest/Least accurate)": 0,
        "1 (Middle ground)": 1,
        "2 (Slowest/Most accurate)": 2,
    }
    return mediapipe_model_complexity_dictionary[mediapipe_model_complexity_value]


def extract_processing_parameter_model_from_tree(parameter_object, value_dictionary: dict = None):
    if value_dictionary is None:
        value_dictionary = {}

    for child in parameter_object.children():
        if child.hasChildren():
            extract_processing_parameter_model_from_tree(child, value_dictionary)
        else:
            value_dictionary[child.name()] = child.value()
    return value_dictionary
