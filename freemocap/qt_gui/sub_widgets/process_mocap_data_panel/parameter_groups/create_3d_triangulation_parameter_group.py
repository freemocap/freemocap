from pyqtgraph.parametertree import Parameter

from freemocap.core_processes.session_processing_parameter_models.session_processing_parameter_models import (
    AniposeTriangulate3DParametersModel,
)


def create_3d_triangulation_prarameter_group(
    parameter_model: AniposeTriangulate3DParametersModel = AniposeTriangulate3DParametersModel(),
) -> Parameter:

    return Parameter.create(
        name="Anipose Triangulation",
        type="group",
        children=[
            dict(
                name="Confidence Threshold Cut-off",
                type="float",
                value=parameter_model.confidence_threshold_cutoff,
                tip="Confidence threshold cut-off for triangulation. "
                "NOTE - Never trust a machine learning model's estimates of their own confidence! "
                "TODO - Something similar that uses `reprojection_error` instead of `confidence`",
            ),
            dict(
                name="Use RANSAC Method",
                type="bool",
                value=parameter_model.use_triangulate_ransac_method,
                tip="If true, use `anipose`'s `triangulate_ransac` method instead of the default `triangulate_simple` method. "
                "NOTE - Much slower than the 'simple' method, but might be more accurate and better at rejecting bad camera views. Needs more testing and evaluation to see if it's worth it. ",
            ),
        ],
    )
