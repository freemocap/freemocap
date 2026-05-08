from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.tasks.triangulation.helpers.default_triangulation_values import DEFAULT_MIN_CAMERAS, \
    DEFAULT_MAX_CAMERAS_TO_DROP, DEFAULT_TARGET_REPROJECTION_ERROR


class TriangulationConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    use_outlier_rejection: bool = Field(
        default=True,
        alias="useOutlierRejection",
        description=(
            "If True, triangulation uses the subset-ensemble outlier-rejection method: "
            "for each 3D point, the algorithm triangulates with all cameras, then iteratively "
            "drops cameras to find subsets that lower the reprojection error, and returns an "
            "exponentially-weighted average of all candidate 3D points along with per-camera "
            "confidence weights. Robust to mistracked or partially occluded cameras at extra "
            "compute cost (combinations x n_points per frame). "
            "If False, triangulation uses plain DLT - fast, but a single bad observation can "
            "skew the 3D estimate."
        ),
    )
    minimum_cameras_for_triangulation: int = Field(
        default=DEFAULT_MIN_CAMERAS,
        alias="minimumCamerasForTriangulation",
        ge=2,
        description=(
            "Minimum number of valid camera observations required to triangulate a point. "
            "Points seen by fewer cameras are returned as NaN. DLT is geometrically defined "
            "for >=2 cameras, but >=3 is recommended when use_outlier_rejection=True so that "
            "dropping a camera still leaves a well-conditioned solve."
        ),
    )
    maximum_cameras_to_drop: int = Field(
        default=DEFAULT_MAX_CAMERAS_TO_DROP,
        alias="maximumCamerasToDrop",
        ge=0,
        description=(
            "Maximum number of cameras the outlier-rejection method is allowed to drop "
            "when searching for a better subset. Higher values explore more combinations "
            "(C(n_cameras, n_cameras - k)) and can recover from more simultaneous outliers, "
            "but cost grows combinatorially. Ignored when use_outlier_rejection=False."
        ),
    )
    target_reprojection_error: float = Field(
        default=DEFAULT_TARGET_REPROJECTION_ERROR,
        alias="targetReprojectionError",
        gt=0.0,
        description=(
            "Target mean reprojection error, expressed in undistorted-normalized image "
            "coordinates (typical range ~[-1, 1], so ~0.01 ~= 1% of the image plane). "
            "Subset weights decay as exp(-5 * mean_error / target). Smaller values weight "
            "low-error subsets more aggressively; larger values produce a softer average. "
            "Also acts as the early-exit threshold: if the all-cameras triangulation already "
            "achieves this error, no subsets are tried. Ignored when use_outlier_rejection=False."
        ),
    )
