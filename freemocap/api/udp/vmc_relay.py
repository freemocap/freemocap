"""
VMC relay: app-level async task that broadcasts rigid body poses over UDP.

Runs independently of any browser/WebSocket connection. Polls the
application's frontend payload pipeline for new frames and sends
bone transforms via the VMC protocol.

The relay lazily creates and destroys its VMCSender based on the
live VMCSettings — toggling VMC on/off in the UI takes effect
within one poll cycle (~10ms).

Started by the FastAPI app lifespan and cancelled on shutdown.
"""
import asyncio
import logging

from freemocap.app.freemocap_application import FreemocapApplication, get_freemocap_app
from freemocap.app.settings import SettingsManager
from freemocap.core.mocap.skeleton_dewiggler.vmc_sender import VMCSender
from freemocap.core.viz.frontend_payload import FrontendPayload
from freemocap.utilities.wait_functions import await_10ms

logger = logging.getLogger(__name__)


async def vmc_relay_task(
    *,
    app: FreemocapApplication,
) -> None:
    """Poll for new frames and broadcast rigid body poses via VMC/UDP.

    This task mirrors the websocket relay's polling pattern but sends
    over UDP instead of WebSocket, and runs regardless of whether any
    browser is connected.

    Args:
        app: The FreemocapApplication singleton (owns pipelines + settings).
    """
    settings_manager: SettingsManager = app.settings_manager
    sender: VMCSender | None = None
    last_sent_frame: int = -1

    logger.info("VMC relay task started")

    try:
        while app.should_continue:
            await await_10ms()

            # Sync sender lifecycle with settings
            vmc_settings = settings_manager.settings.vmc
            if vmc_settings.enabled:
                if (
                    sender is None
                    or sender._host != vmc_settings.host
                    or sender._port != vmc_settings.port
                ):
                    if sender is not None:
                        sender.close()
                    sender = VMCSender(host=vmc_settings.host, port=vmc_settings.port)
            else:
                if sender is not None:
                    sender.close()
                    sender = None
                continue  # Nothing to do when disabled

            # Poll for new frames
            try:
                frontend_payloads = app.get_latest_frontend_payloads(
                    if_newer_than=last_sent_frame,
                )
            except IndexError:
                last_sent_frame = -1
                continue

            for _pipeline_id, (_payload_bytes, frontend_payload) in frontend_payloads.items():
                if not isinstance(frontend_payload, FrontendPayload):
                    continue
                if frontend_payload.rigid_body_poses:
                    sender.send(frontend_payload.rigid_body_poses)
                last_sent_frame = frontend_payload.frame_number

    except asyncio.CancelledError:
        logger.info("VMC relay task cancelled")
    except Exception as e:
        logger.error(f"VMC relay task error: {e}", exc_info=True)
        raise
    finally:
        if sender is not None:
            sender.close()
        logger.info("VMC relay task stopped")
