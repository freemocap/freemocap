"""
WebSocket settings protocol: handles settings/patch, settings/request,
and pushes settings/state on changes.

Runs as a task in WebsocketServer.run() alongside the existing
_frontend_image_relay, _logs_relay, and _client_message_handler tasks.
"""
import asyncio
import logging
from copy import deepcopy

from starlette.websockets import WebSocket, WebSocketState

from freemocap.app.freemocap_application import FreemocapApplication
from freemocap.app.settings import SettingsManager

logger = logging.getLogger(__name__)


async def settings_state_relay(
    websocket: WebSocket,
    settings_manager: SettingsManager,
    should_continue: callable,
) -> None:
    """
    Push `settings/state` to the frontend whenever settings change.

    Sends the full blob on startup (so the frontend gets initial state),
    then awaits the SettingsManager's change event and pushes again.
    """
    try:
        # Push initial state on connection
        if websocket.client_state == WebSocketState.CONNECTED:
            state_msg = settings_manager.get_state_message()
            await websocket.send_json(state_msg)
            logger.info("Sent initial settings/state")

        # Push on every subsequent change
        while should_continue():
            await settings_manager.wait_for_change()
            if websocket.client_state != WebSocketState.CONNECTED:
                break
            state_msg = settings_manager.get_state_message()
            await websocket.send_json(state_msg)
            logger.debug("Pushed settings/state")

    except asyncio.CancelledError:
        logger.debug("Settings state relay task cancelled")
    except Exception as e:
        logger.exception(f"Error in settings state relay: {e.__class__.__name__}: {e}")
        raise


def handle_settings_message(
    data: dict,
    settings_manager: SettingsManager,
    app: FreemocapApplication,
) -> None:
    """
    Handle an incoming settings-related WebSocket message.

    Called from _client_message_handler when message_type starts with 'settings/'.

    Supported message_types:
      - settings/patch: apply a partial update to settings
      - settings/request: trigger a full state push (handled by notify)
    """
    message_type = data.get("message_type", "")

    if message_type == "settings/patch":
        patch = data.get("patch")
        if patch is None:
            raise ValueError("Received settings/patch with no 'patch' field")
        settings_manager.apply_patch(patch)
        # After applying config changes, sync relevant configs back
        # to the running pipelines/managers
        _sync_patch_to_app(patch=patch, settings_manager=settings_manager, app=app)

    elif message_type == "settings/request":
        # Frontend wants the full state — just notify so the relay task pushes it
        settings_manager.notify_changed()

    else:
        raise ValueError(f"Unknown settings message_type: {message_type}")


def _sync_patch_to_app(
    patch: dict,
    settings_manager: SettingsManager,
    app: FreemocapApplication,
) -> None:
    """
    After a settings patch is applied, push relevant config changes
    into the running application components.

    This bridges the gap between "settings blob updated" and
    "actual pipeline/camera behavior changed."
    """
    # If calibration config was patched, update active pipelines
    if "calibration" in patch and "config" in patch.get("calibration", {}):
        cal_config = settings_manager.settings.calibration.config
        with app.realtime_pipeline_manager.lock:
            for pipeline in app.realtime_pipeline_manager.pipelines.values():
                new_config = deepcopy(pipeline.config)
                new_config.calibration_config = cal_config
                pipeline.update_config(new_config=new_config)
        logger.info("Synced calibration config to active pipelines")

    # If mocap config was patched, update active pipelines
    if "mocap" in patch and "config" in patch.get("mocap", {}):
        mocap_config = settings_manager.settings.mocap.config
        with app.realtime_pipeline_manager.lock:
            for pipeline in app.realtime_pipeline_manager.pipelines.values():
                new_config = deepcopy(pipeline.config)
                new_config.mocap_config = mocap_config
                pipeline.update_config(new_config=new_config)
        logger.info("Synced mocap config to active pipelines")

    # Camera config changes still go through the REST
    # /camera/group/apply endpoint for now.
