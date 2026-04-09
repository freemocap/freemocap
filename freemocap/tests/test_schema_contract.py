"""
Schema contract tests: verify backend Pydantic models serialize to the shapes
the frontend TypeScript types expect.

These catch field name drift, missing fields, and default value mismatches
between the Python backend and the React frontend.
"""

from freemocap.core.pipeline.pipeline_configs import (
    CalibrationPipelineConfig,
    CalibrationSolverMethod,
    MocapPipelineConfig,
)

from freemocap.app.settings import (
    CalibrationSettings,
    CameraState,
    CameraStatus,
    FreeMoCapSettings,
    MocapSettings,
    PipelineSettings,
    SettingsManager,
    VMCSettings,
)
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.bone_length_estimator import EstimatorConfig
from freemocap.core.tasks.mocap.skeleton_dewiggler.realtime_skeleton_filter import RealtimeFilterConfig


# ---------------------------------------------------------------------------
# Top-level settings blob
# ---------------------------------------------------------------------------


class TestFreeMoCapSettingsSchema:
    """Verify the top-level FreeMoCapSettings matches the frontend
    FreeMoCapSettings interface in settings-types.ts."""

    def test_has_expected_top_level_keys(self) -> None:
        dumped = FreeMoCapSettings().model_dump()
        expected_keys = {"cameras", "pipeline", "calibration", "mocap", "vmc"}
        assert set(dumped.keys()) == expected_keys

    def test_cameras_defaults_to_empty_dict(self) -> None:
        dumped = FreeMoCapSettings().model_dump()
        assert dumped["cameras"] == {}

    def test_pipeline_is_dict(self) -> None:
        dumped = FreeMoCapSettings().model_dump()
        assert isinstance(dumped["pipeline"], dict)

    def test_calibration_is_dict(self) -> None:
        dumped = FreeMoCapSettings().model_dump()
        assert isinstance(dumped["calibration"], dict)

    def test_mocap_is_dict(self) -> None:
        dumped = FreeMoCapSettings().model_dump()
        assert isinstance(dumped["mocap"], dict)


# ---------------------------------------------------------------------------
# Calibration settings
# ---------------------------------------------------------------------------


class TestCalibrationSettingsSchema:
    """Verify CalibrationSettings matches the frontend
    BackendCalibrationSettings interface."""

    EXPECTED_KEYS = {
        "config",
        "is_recording",
        "recording_progress",
        "last_recording_path",
        "has_calibration_toml",
    }

    def test_has_expected_keys(self) -> None:
        dumped = CalibrationSettings().model_dump()
        assert set(dumped.keys()) == self.EXPECTED_KEYS

    def test_default_is_recording_false(self) -> None:
        dumped = CalibrationSettings().model_dump()
        assert dumped["is_recording"] is False

    def test_default_recording_progress_zero(self) -> None:
        dumped = CalibrationSettings().model_dump()
        assert dumped["recording_progress"] == 0.0

    def test_default_last_recording_path_none(self) -> None:
        dumped = CalibrationSettings().model_dump()
        assert dumped["last_recording_path"] is None

    def test_default_has_calibration_toml_false(self) -> None:
        dumped = CalibrationSettings().model_dump()
        assert dumped["has_calibration_toml"] is False


class TestCalibrationConfigSchema:
    """Verify CalibrationPipelineConfig serializes to the shape
    the frontend BackendCalibrationConfig interface expects.

    The frontend settings-types.ts uses snake_case field names,
    which is what model_dump() produces by default."""

    EXPECTED_KEYS = {
        "calibration_recording_folder",
        "charuco_board_x_squares",
        "charuco_board_y_squares",
        "charuco_square_length",
        "solver_method",
        "use_groundplane",
        "pyceres_solver_config",
    }

    def test_has_expected_keys(self) -> None:
        dumped = CalibrationPipelineConfig().model_dump()
        assert set(dumped.keys()) == self.EXPECTED_KEYS

    def test_by_alias_produces_camel_case(self) -> None:
        """The HTTP endpoints receive camelCase from frontend thunks.
        Verify by_alias=True produces the expected alias names."""
        dumped = CalibrationPipelineConfig().model_dump(by_alias=True)
        assert "charucoBoardXSquares" in dumped
        assert "charucoBoardYSquares" in dumped
        assert "charucoSquareLength" in dumped
        assert "solverMethod" in dumped
        assert "useGroundplane" in dumped

    def test_default_charuco_board_x_squares(self) -> None:
        """Frontend initialState has charucoBoardXSquares: 5."""
        config = CalibrationPipelineConfig()
        assert config.charuco_board_x_squares == 5

    def test_default_charuco_board_y_squares(self) -> None:
        """Frontend initialState has charucoBoardYSquares: 3."""
        config = CalibrationPipelineConfig()
        assert config.charuco_board_y_squares == 3

    def test_default_charuco_square_length(self) -> None:
        """Frontend initialState has charucoSquareLength: 1."""
        config = CalibrationPipelineConfig()
        assert config.charuco_square_length == 1

    def test_default_solver_method(self) -> None:
        """Frontend initialState has solverMethod: 'anipose'."""
        config = CalibrationPipelineConfig()
        assert config.solver_method == CalibrationSolverMethod.ANIPOSE
        assert config.solver_method.value == "anipose"

    def test_default_use_groundplane(self) -> None:
        """Frontend initialState has useGroundplane: false."""
        config = CalibrationPipelineConfig()
        assert config.use_groundplane is False

    def test_roundtrip_snake_case(self) -> None:
        """model_dump() → model_validate() round-trips cleanly with snake_case.
        This is the path used by SettingsManager.apply_patch."""
        original = CalibrationPipelineConfig()
        dumped = original.model_dump()
        restored = CalibrationPipelineConfig.model_validate(dumped)
        assert restored.charuco_board_x_squares == original.charuco_board_x_squares
        assert restored.charuco_board_y_squares == original.charuco_board_y_squares
        assert restored.solver_method == original.solver_method

    def test_roundtrip_camel_case(self) -> None:
        """model_dump(by_alias=True) → model_validate() round-trips cleanly
        with camelCase aliases. This is the path used by HTTP endpoints."""
        original = CalibrationPipelineConfig()
        dumped = original.model_dump(by_alias=True)
        restored = CalibrationPipelineConfig.model_validate(dumped)
        assert restored.charuco_board_x_squares == original.charuco_board_x_squares


# ---------------------------------------------------------------------------
# Mocap settings
# ---------------------------------------------------------------------------


class TestMocapSettingsSchema:
    """Verify MocapSettings matches the frontend BackendMocapSettings."""

    EXPECTED_KEYS = {
        "config",
        "is_recording",
        "recording_progress",
        "last_recording_path",
    }

    def test_has_expected_keys(self) -> None:
        dumped = MocapSettings().model_dump()
        assert set(dumped.keys()) == self.EXPECTED_KEYS

    def test_default_is_recording_false(self) -> None:
        dumped = MocapSettings().model_dump()
        assert dumped["is_recording"] is False


class TestMocapConfigSchema:
    """Verify MocapPipelineConfig matches the frontend BackendMocapConfig."""

    EXPECTED_KEYS = {"detector", "skeleton_filter"}

    def test_has_expected_keys(self) -> None:
        config = MocapPipelineConfig.default_realtime()
        dumped = config.model_dump()
        assert set(dumped.keys()) == self.EXPECTED_KEYS

    def test_detector_is_dict(self) -> None:
        config = MocapPipelineConfig.default_realtime()
        dumped = config.model_dump()
        assert isinstance(dumped["detector"], dict)

    def test_skeleton_filter_is_dict(self) -> None:
        config = MocapPipelineConfig.default_realtime()
        dumped = config.model_dump()
        assert isinstance(dumped["skeleton_filter"], dict)


class TestRealtimeFilterConfigSchema:
    """Verify RealtimeFilterConfig matches the frontend BackendRealtimeFilterConfig."""

    EXPECTED_KEYS = {
        "min_cutoff",
        "beta",
        "d_cutoff",
        "fabrik_tolerance",
        "fabrik_max_iterations",
        "height_meters",
        "noise_sigma",
        "estimator_config",
        "max_reprojection_error_px",
        "max_velocity_m_per_s",
        "max_rejected_streak",
        "max_prediction_frames",
        "prediction_velocity_decay",
    }

    def test_has_expected_keys(self) -> None:
        dumped = RealtimeFilterConfig().model_dump()
        assert set(dumped.keys()) == self.EXPECTED_KEYS

    def test_estimator_config_keys(self) -> None:
        """Frontend BackendEstimatorConfig expects these three fields."""
        dumped = RealtimeFilterConfig().model_dump()
        estimator = dumped["estimator_config"]
        assert set(estimator.keys()) == {
            "max_samples",
            "min_samples_for_full_confidence",
            "iqr_confidence_sensitivity",
        }

    def test_default_min_cutoff_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has min_cutoff: 0.005."""
        assert RealtimeFilterConfig().min_cutoff == 0.005

    def test_default_beta_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has beta: 0.3."""
        assert RealtimeFilterConfig().beta == 0.3

    def test_default_d_cutoff_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has d_cutoff: 1.0."""
        assert RealtimeFilterConfig().d_cutoff == 1.0

    def test_default_fabrik_tolerance_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has fabrik_tolerance: 1e-4."""
        assert RealtimeFilterConfig().fabrik_tolerance == 1e-4

    def test_default_fabrik_max_iterations_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has fabrik_max_iterations: 20."""
        assert RealtimeFilterConfig().fabrik_max_iterations == 20

    def test_default_height_meters_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has height_meters: 1.75."""
        assert RealtimeFilterConfig().height_meters == 1.75

    def test_default_noise_sigma_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has noise_sigma: 0.015."""
        assert RealtimeFilterConfig().noise_sigma == 0.015

    def test_default_max_reprojection_error_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has max_reprojection_error_px: 60.0."""
        assert RealtimeFilterConfig().max_reprojection_error_px == 60.0

    def test_default_max_velocity_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has max_velocity_m_per_s: 50.0."""
        assert RealtimeFilterConfig().max_velocity_m_per_s == 50.0

    def test_default_max_rejected_streak_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has max_rejected_streak: 5."""
        assert RealtimeFilterConfig().max_rejected_streak == 5

    def test_default_max_prediction_frames_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has max_prediction_frames: 15."""
        assert RealtimeFilterConfig().max_prediction_frames == 15

    def test_default_prediction_velocity_decay_matches_frontend(self) -> None:
        """Frontend DEFAULT_REALTIME_FILTER_CONFIG has prediction_velocity_decay: 0.75."""
        assert RealtimeFilterConfig().prediction_velocity_decay == 0.75


class TestEstimatorConfigDefaults:
    """Verify EstimatorConfig defaults match frontend DEFAULT_ESTIMATOR_CONFIG."""

    def test_default_max_samples(self) -> None:
        assert EstimatorConfig().max_samples == 500

    def test_default_min_samples_for_full_confidence(self) -> None:
        assert EstimatorConfig().min_samples_for_full_confidence == 100

    def test_default_iqr_confidence_sensitivity(self) -> None:
        assert EstimatorConfig().iqr_confidence_sensitivity == 10.0


# ---------------------------------------------------------------------------
# Pipeline settings
# ---------------------------------------------------------------------------


class TestPipelineSettingsSchema:
    """Verify PipelineSettings matches the frontend BackendPipelineSettings."""

    EXPECTED_KEYS = {
        "config",
        "is_connected",
        "pipeline_id",
        "camera_group_id",
        "is_paused",
    }

    def test_has_expected_keys(self) -> None:
        dumped = PipelineSettings().model_dump()
        assert set(dumped.keys()) == self.EXPECTED_KEYS

    def test_default_is_connected_false(self) -> None:
        dumped = PipelineSettings().model_dump()
        assert dumped["is_connected"] is False

    def test_default_is_paused_false(self) -> None:
        dumped = PipelineSettings().model_dump()
        assert dumped["is_paused"] is False


# ---------------------------------------------------------------------------
# Camera state
# ---------------------------------------------------------------------------


class TestCameraStateSchema:
    """Verify CameraState matches the frontend BackendCameraState."""

    def test_has_config_and_status(self) -> None:
        # CameraState requires a CameraConfig — we just check it has the right top-level shape
        from skellycam.core.camera.config.camera_config import CameraConfig

        state = CameraState(config=CameraConfig(camera_id="0"), status=CameraStatus.CONNECTED)
        dumped = state.model_dump()
        assert "config" in dumped
        assert "status" in dumped

    def test_status_values_match_frontend(self) -> None:
        """Frontend BackendCameraStatus = "disconnected" | "connected" | "error"."""
        assert CameraStatus.DISCONNECTED.value == "disconnected"
        assert CameraStatus.CONNECTED.value == "connected"
        assert CameraStatus.ERROR.value == "error"


# ---------------------------------------------------------------------------
# Settings state message (WebSocket)
# ---------------------------------------------------------------------------


class TestSettingsStateMessageFormat:
    """Verify the WebSocket settings/state message has the shape
    the frontend isSettingsStateMessage() type guard expects."""

    def test_has_required_fields(self) -> None:
        manager = SettingsManager()
        msg = manager.get_state_message()
        assert msg["message_type"] == "settings/state"
        assert isinstance(msg["settings"], dict)
        assert isinstance(msg["version"], int)

    def test_settings_field_is_full_blob(self) -> None:
        manager = SettingsManager()
        msg = manager.get_state_message()
        settings = msg["settings"]
        assert "cameras" in settings
        assert "pipeline" in settings
        assert "calibration" in settings
        assert "mocap" in settings

    def test_initial_version_is_zero(self) -> None:
        manager = SettingsManager()
        msg = manager.get_state_message()
        assert msg["version"] == 0


# ---------------------------------------------------------------------------
# Calibration solver method enum
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# VMC settings
# ---------------------------------------------------------------------------


class TestVMCSettingsSchema:
    """Verify VMCSettings matches the frontend (once a frontend VMC type is added)."""

    EXPECTED_KEYS = {"enabled", "host", "port"}

    def test_has_expected_keys(self) -> None:
        dumped = VMCSettings().model_dump()
        assert set(dumped.keys()) == self.EXPECTED_KEYS

    def test_default_enabled_false(self) -> None:
        assert VMCSettings().enabled is False

    def test_default_host(self) -> None:
        assert VMCSettings().host == "127.0.0.1"

    def test_default_port(self) -> None:
        assert VMCSettings().port == 39539


# ---------------------------------------------------------------------------
# Calibration solver method enum
# ---------------------------------------------------------------------------


class TestCalibrationSolverMethodEnum:
    """Verify the enum values match frontend CalibrationSolverMethod type."""

    def test_anipose_value(self) -> None:
        assert CalibrationSolverMethod.ANIPOSE.value == "anipose"

    def test_pyceres_value(self) -> None:
        assert CalibrationSolverMethod.PYCERES.value == "pyceres"

    def test_only_two_members(self) -> None:
        assert len(CalibrationSolverMethod) == 2
