"""
SettingsManager unit tests: patch logic, version tracking, deep merge,
and async change notification.
"""
import asyncio
import copy

import pytest

from freemocap.app.settings import (
    CalibrationSettings,
    FreeMoCapSettings,
    MocapSettings,
    SettingsManager,
    _deep_merge,
)


# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------


class TestDeepMerge:

    def test_scalar_overwrite(self) -> None:
        base = {"a": 1, "b": 2}
        patch = {"b": 99}
        result = _deep_merge(base=base, patch=patch)
        assert result == {"a": 1, "b": 99}

    def test_nested_merge(self) -> None:
        base = {"outer": {"a": 1, "b": 2}}
        patch = {"outer": {"b": 99}}
        result = _deep_merge(base=base, patch=patch)
        assert result == {"outer": {"a": 1, "b": 99}}

    def test_deeply_nested_merge(self) -> None:
        base = {"l1": {"l2": {"l3": {"keep": True, "change": False}}}}
        patch = {"l1": {"l2": {"l3": {"change": True}}}}
        result = _deep_merge(base=base, patch=patch)
        assert result["l1"]["l2"]["l3"]["keep"] is True
        assert result["l1"]["l2"]["l3"]["change"] is True

    def test_adds_new_keys(self) -> None:
        base = {"a": 1}
        patch = {"b": 2}
        result = _deep_merge(base=base, patch=patch)
        assert result == {"a": 1, "b": 2}

    def test_does_not_mutate_base(self) -> None:
        base = {"outer": {"a": 1}}
        base_copy = copy.deepcopy(base)
        _deep_merge(base=base, patch={"outer": {"a": 99}})
        assert base == base_copy

    def test_does_not_mutate_patch(self) -> None:
        patch = {"outer": {"a": 99}}
        patch_copy = copy.deepcopy(patch)
        _deep_merge(base={"outer": {"a": 1}}, patch=patch)
        assert patch == patch_copy

    def test_empty_patch_returns_base_copy(self) -> None:
        base = {"a": 1}
        result = _deep_merge(base=base, patch={})
        assert result == base
        assert result is not base

    def test_empty_base(self) -> None:
        result = _deep_merge(base={}, patch={"a": 1})
        assert result == {"a": 1}

    def test_replaces_dict_with_scalar(self) -> None:
        """If patch has a scalar where base has a dict, scalar wins."""
        base = {"a": {"nested": True}}
        patch = {"a": "replaced"}
        result = _deep_merge(base=base, patch=patch)
        assert result["a"] == "replaced"


# ---------------------------------------------------------------------------
# SettingsManager: initial state
# ---------------------------------------------------------------------------


class TestSettingsManagerInitialState:

    def test_initial_version_is_zero(self) -> None:
        manager = SettingsManager()
        assert manager.version == 0

    def test_initial_settings_is_default(self) -> None:
        manager = SettingsManager()
        assert manager.settings == FreeMoCapSettings()

    def test_initial_cameras_empty(self) -> None:
        manager = SettingsManager()
        assert manager.settings.cameras == {}

    def test_initial_calibration_not_recording(self) -> None:
        manager = SettingsManager()
        assert manager.settings.calibration.is_recording is False

    def test_initial_mocap_not_recording(self) -> None:
        manager = SettingsManager()
        assert manager.settings.mocap.is_recording is False


# ---------------------------------------------------------------------------
# SettingsManager: apply_patch
# ---------------------------------------------------------------------------


class TestSettingsManagerApplyPatch:

    def test_bumps_version(self) -> None:
        manager = SettingsManager()
        assert manager.version == 0
        manager.apply_patch({"calibration": {"is_recording": True}})
        assert manager.version == 1
        manager.apply_patch({"calibration": {"is_recording": False}})
        assert manager.version == 2

    def test_patch_calibration_recording_status(self) -> None:
        manager = SettingsManager()
        manager.apply_patch({"calibration": {"is_recording": True}})
        assert manager.settings.calibration.is_recording is True

    def test_patch_calibration_config_field(self) -> None:
        manager = SettingsManager()
        manager.apply_patch({
            "calibration": {"config": {"charuco_board_x_squares": 7}},
        })
        assert manager.settings.calibration.config.charuco_board_x_squares == 7

    def test_patch_preserves_sibling_fields(self) -> None:
        """Patching charuco_board_x_squares should not clobber charuco_board_y_squares."""
        manager = SettingsManager()
        original_y = manager.settings.calibration.config.charuco_board_y_squares
        manager.apply_patch({
            "calibration": {"config": {"charuco_board_x_squares": 7}},
        })
        assert manager.settings.calibration.config.charuco_board_y_squares == original_y

    def test_patch_preserves_unrelated_sections(self) -> None:
        """Patching calibration should not touch mocap."""
        manager = SettingsManager()
        original_mocap = manager.settings.mocap.model_dump()
        manager.apply_patch({"calibration": {"is_recording": True}})
        assert manager.settings.mocap.model_dump() == original_mocap

    def test_patch_mocap_config(self) -> None:
        manager = SettingsManager()
        manager.apply_patch({
            "mocap": {"is_recording": True},
        })
        assert manager.settings.mocap.is_recording is True

    def test_patch_returns_new_settings(self) -> None:
        manager = SettingsManager()
        result = manager.apply_patch({"calibration": {"is_recording": True}})
        assert isinstance(result, FreeMoCapSettings)
        assert result.calibration.is_recording is True

    def test_patch_with_invalid_data_raises(self) -> None:
        """Pydantic validation should reject nonsense values."""
        manager = SettingsManager()
        original_version = manager.version
        with pytest.raises(Exception):
            manager.apply_patch({"calibration": "not_a_dict"})
        # Version should NOT have bumped on failure
        assert manager.version == original_version

    def test_patch_with_invalid_data_preserves_state(self) -> None:
        manager = SettingsManager()
        original = manager.settings.model_dump()
        try:
            manager.apply_patch({"calibration": "not_a_dict"})
        except Exception:
            pass
        assert manager.settings.model_dump() == original


# ---------------------------------------------------------------------------
# SettingsManager: get_state_message
# ---------------------------------------------------------------------------


class TestSettingsManagerGetStateMessage:

    def test_message_type(self) -> None:
        manager = SettingsManager()
        msg = manager.get_state_message()
        assert msg["message_type"] == "settings/state"

    def test_includes_version(self) -> None:
        manager = SettingsManager()
        msg = manager.get_state_message()
        assert msg["version"] == 0

    def test_version_reflects_patches(self) -> None:
        manager = SettingsManager()
        manager.apply_patch({"calibration": {"is_recording": True}})
        msg = manager.get_state_message()
        assert msg["version"] == 1

    def test_settings_is_serializable_dict(self) -> None:
        manager = SettingsManager()
        msg = manager.get_state_message()
        settings = msg["settings"]
        assert isinstance(settings, dict)
        assert "cameras" in settings
        assert "pipeline" in settings
        assert "calibration" in settings
        assert "mocap" in settings


# ---------------------------------------------------------------------------
# SettingsManager: update_calibration_status
# ---------------------------------------------------------------------------


class TestSettingsManagerCalibrationStatus:

    def test_set_is_recording(self) -> None:
        manager = SettingsManager()
        manager.update_calibration_status(is_recording=True)
        assert manager.settings.calibration.is_recording is True

    def test_set_recording_progress(self) -> None:
        manager = SettingsManager()
        manager.update_calibration_status(recording_progress=42.5)
        assert manager.settings.calibration.recording_progress == 42.5

    def test_set_last_recording_path(self) -> None:
        manager = SettingsManager()
        manager.update_calibration_status(last_recording_path="/tmp/cal")
        assert manager.settings.calibration.last_recording_path == "/tmp/cal"

    def test_set_has_calibration_toml(self) -> None:
        manager = SettingsManager()
        manager.update_calibration_status(has_calibration_toml=True)
        assert manager.settings.calibration.has_calibration_toml is True

    def test_bumps_version(self) -> None:
        manager = SettingsManager()
        manager.update_calibration_status(is_recording=True)
        assert manager.version == 1

    def test_none_args_leave_fields_unchanged(self) -> None:
        manager = SettingsManager()
        manager.update_calibration_status(is_recording=True)
        manager.update_calibration_status(recording_progress=50.0)
        assert manager.settings.calibration.is_recording is True


# ---------------------------------------------------------------------------
# SettingsManager: update_mocap_status
# ---------------------------------------------------------------------------


class TestSettingsManagerMocapStatus:

    def test_set_is_recording(self) -> None:
        manager = SettingsManager()
        manager.update_mocap_status(is_recording=True)
        assert manager.settings.mocap.is_recording is True

    def test_set_recording_progress(self) -> None:
        manager = SettingsManager()
        manager.update_mocap_status(recording_progress=75.0)
        assert manager.settings.mocap.recording_progress == 75.0

    def test_set_last_recording_path(self) -> None:
        manager = SettingsManager()
        manager.update_mocap_status(last_recording_path="/tmp/mocap")
        assert manager.settings.mocap.last_recording_path == "/tmp/mocap"

    def test_bumps_version(self) -> None:
        manager = SettingsManager()
        manager.update_mocap_status(is_recording=True)
        assert manager.version == 1


# ---------------------------------------------------------------------------
# SettingsManager: async change notification
# ---------------------------------------------------------------------------


class TestSettingsManagerChangeNotification:

    @pytest.mark.asyncio
    async def test_notify_changed_wakes_waiter(self) -> None:
        manager = SettingsManager()
        woke_up = False

        async def waiter() -> None:
            nonlocal woke_up
            await manager.wait_for_change()
            woke_up = True

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)  # Let the waiter start waiting
        assert not woke_up

        manager.notify_changed()
        await asyncio.sleep(0.01)  # Let the waiter wake
        assert woke_up
        await task

    @pytest.mark.asyncio
    async def test_apply_patch_wakes_waiter(self) -> None:
        manager = SettingsManager()
        woke_up = False

        async def waiter() -> None:
            nonlocal woke_up
            await manager.wait_for_change()
            woke_up = True

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)

        manager.apply_patch({"calibration": {"is_recording": True}})
        await asyncio.sleep(0.01)
        assert woke_up
        await task

    @pytest.mark.asyncio
    async def test_update_status_wakes_waiter(self) -> None:
        manager = SettingsManager()
        woke_up = False

        async def waiter() -> None:
            nonlocal woke_up
            await manager.wait_for_change()
            woke_up = True

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)

        manager.update_calibration_status(is_recording=True)
        await asyncio.sleep(0.01)
        assert woke_up
        await task
