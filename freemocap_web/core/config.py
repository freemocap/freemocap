from dataclasses import dataclass


@dataclass
class MediaPipe:
    model_complexity: int
    min_detection_confidence: float
    min_tracking_confidence: float
    static_image_mode: bool
    skip_2d_image_tracking: bool
    use_multiprocessing: bool


@dataclass
class AniPose:
    confidence_threshold_cutoff: float
    use_triangulate_ransac_method: bool
    skip_3d_triangulation: bool


@dataclass
class ButterworthFilterParametersModel:
    sampling_rate: float = 30
    cutoff_frequency: float = 7
    order: int = 4


@dataclass
class PostProcessing:
    frame_rate: float
    butterworth_filter_parameters: ButterworthFilterParametersModel
    max_gap_to_fill: int
    skip_butterworth_filter: bool


@dataclass
class Config:
    MediaPipe: MediaPipe
    AniPose: AniPose
    PostProcessing: PostProcessing
    arbitrary_types_allowed: bool
    use_tqdm: bool

    @staticmethod
    def default():
        return Config(
            MediaPipe(
                model_complexity=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                static_image_mode=False,
                skip_2d_image_tracking=False,
                use_multiprocessing=False),
            AniPose(
                confidence_threshold_cutoff=0.5,
                use_triangulate_ransac_method=False,
                skip_3d_triangulation=False),
            PostProcessing(
                frame_rate=30.0,
                butterworth_filter_parameters=ButterworthFilterParametersModel(
                    sampling_rate=30,
                    cutoff_frequency=7,
                    order=4),
                max_gap_to_fill=10,
                skip_butterworth_filter=False),
            arbitrary_types_allowed=True,
            use_tqdm=True)


