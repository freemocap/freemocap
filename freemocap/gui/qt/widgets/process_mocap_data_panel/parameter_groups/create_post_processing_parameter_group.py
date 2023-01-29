from pyqtgraph.parametertree import Parameter

from freemocap.core_processes.session_processing_parameter_models.session_processing_parameter_models import (
    PostProcessingParametersModel,
)


def create_post_processing_parameter_group(
    parameter_model: PostProcessingParametersModel = PostProcessingParametersModel(),
) -> Parameter:

    return Parameter.create(
        name="Butterworth Filter",
        type="group",
        children=[
            dict(
                name="framerate",
                type="float",
                value=parameter_model.butterworth_filter_parameters.sampling_rate,
                tip="Framerate of the recording " "TODO - Calculate this from the recorded timestamps....",
            ),
            dict(
                name="Cutoff Frequency",
                type="float",
                value=parameter_model.butterworth_filter_parameters.cutoff_frequency,
                tip="Oscillations above this frequency will be filtered from the data. ",
            ),
            dict(
                name="Order",
                type="int",
                value=parameter_model.butterworth_filter_parameters.order,
                tip="Order of the filter."
                "NOTE - I'm not really sure what this parameter does, but this is what I see in other people's Methods sections so....   lol",
            ),
        ],
        tip="Low-pass, zero-lag, Butterworth filter to remove high frequency oscillations/noise from the data. ",
    )
