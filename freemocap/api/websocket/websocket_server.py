"""
WebSocket server — the per-connection supervisor of the self-describing message
stream.

Thin supervisor for one WebSocket connection: composes the message send path
(SendSerializer + FrameRelay) with the replace-kind emitters (convention, model,
camera_layout), the log relay, the app-state sender, the posthoc-progress
sender, and the inbound client-message handler (display sizes). The FrameRelay
is the ONE consumer of the pipeline's aggregator output; the camera images ride
each frame message's image field. Flow control is newest-wins — there is no ack
window; the inbound frameAcknowledgment carries displayImageSizes only (they
drive SkellyCam's JPEG downscaling).

The replace-kinds are emitted on connect and re-emitted whole whenever the data
model changes (pipeline start/stop, detector, camera set) — one composite
signature, not per-cause checks. "Camera-only" vs "camera + reconstruction" is
two message sets produced by one mechanism.
"""
import asyncio
import json
import logging
import os
import time
from queue import Empty

from fastapi import FastAPI
from skellycam.api.websocket.websocket_server import ServerFramerateCalculator
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate
from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt
from skellylogs import get_websocket_log_queue
from skellylogs.handlers.websocket_log_queue_handler import MIN_LOG_LEVEL_FOR_WEBSOCKET
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from freemocap.api.websocket.frame_relay import FrameRelay
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.app.freemocap_application import FreemocapApplication, get_freemocap_app
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.message_model import (
    AppStateMessage,
    DetailedFramerate,
    FramerateMessage,
    LogMessage,
    LogRecord,
    ProgressMessage,
    encode_message,
)
from freemocap.core.streaming.producers import signature_of
from freemocap.core.streaming.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names
from freemocap.utilities.wait_functions import await_10ms
from skellyforge.skellymodels.standard_human.standard_human_model import compose_standard_human

logger = logging.getLogger(__name__)


class WebsocketServer:
    def __init__(self, fastapi_app: FastAPI, websocket: WebSocket):
        self.websocket = websocket
        if not hasattr(fastapi_app, "state") or not hasattr(fastapi_app.state, "global_kill_flag"):
            raise RuntimeError(
                "FastAPI app does not have a global_kill_flag in its state"
            )
        self._global_kill_flag = fastapi_app.state.global_kill_flag
        self._app: FreemocapApplication = get_freemocap_app()

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []
        self._display_image_sizes: dict[CameraGroupIdString, dict[str, float]] | None = None

        self._frontend_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._server_framerate_calculators: dict[CameraGroupIdString, ServerFramerateCalculator] = {}
        self._display_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._last_framerate_send_time: float = 0.0

        # ── Standard-stream send path ────────────────────────────────────
        # One writer (the serializer owns the send lock).
        self._serializer = SendSerializer(websocket)
        self._standard_human = compose_standard_human()
        # Config-update subscriptions (one each, keyed) — the replace-kinds
        # re-emit on ANY config change riding the pubsub network.
        self._config_subscriptions: dict[tuple[str, str], object] = {}
        # The relay consumes raw frame contexts via the injected source.
        self._relay = FrameRelay(
            serializer=self._serializer,
            source=self._await_next_frame,
            should_continue=lambda: self.should_continue,
        )
        # The initial composition (may be image-only — the replace-kinds re-emit
        # when the data model changes, e.g. a pipeline starts).
        self._relay.set_composition(self._compose_current())

    # ── Composition lifecycle ──────────────────────────────────────────

    def _build_stream_context(self) -> StreamContext:
        camera_ids = self._current_camera_ids()
        detector_type = self._current_detector_type()
        return StreamContext(
            standard_human=self._standard_human,
            camera_ids=camera_ids,
            camera_image_sizes=self._camera_image_sizes(),
            tracker_keypoint_names=tuple(tracker_keypoint_names(detector_type)),
            detector_type=detector_type,
            pipeline_live=bool(camera_ids),
        )

    def _compose_current(self):
        return compose_messages(self._build_stream_context())

    async def _emit_replace_kinds(self, composition) -> None:
        await self._serializer.send_message(encode_message(composition.convention))
        await self._serializer.send_message(encode_message(composition.model))
        await self._serializer.send_message(encode_message(composition.camera_layout))

    def _refresh_config_subscriptions(self) -> None:
        """Subscribe (once each, keyed) to the config-update topics of every
        live pipeline + its camera group.

        The replace-kinds re-emit on ANY config change riding the existing pubsub
        network: freemocap's ``PipelineConfigUpdateTopic`` (per pipeline) and
        skellycam's ``UPDATE_CAMERA_SETTINGS`` / ``EXTRACTED_CONFIG`` (per
        camera group — the camera workers publish the extracted config when
        they apply a settings change, e.g. a rotation).
        """
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            if not pipeline.alive:
                continue
            pipeline_key = (pipeline.id, "pipeline")
            if pipeline_key not in self._config_subscriptions:
                self._config_subscriptions[pipeline_key] = (
                    pipeline.pipeline_config_subscription
                )
            group_pubsub = pipeline.camera_group.ipc.pubsub
            for topic in (TopicTypes.UPDATE_CAMERA_SETTINGS, TopicTypes.EXTRACTED_CONFIG):
                key = (pipeline.camera_group.id, topic.name)
                if key not in self._config_subscriptions:
                    self._config_subscriptions[key] = group_pubsub.get_subscription(topic)

    def _drain_config_updates(self) -> bool:
        """True if any config-update message arrived since the last drain."""
        got = False
        for subscription in self._config_subscriptions.values():
            while True:
                try:
                    subscription.get_nowait()
                    got = True
                except Empty:
                    break
        return got

    async def _ensure_composition(self) -> None:
        """Rebuild + re-emit the replace-kinds when the data model changed.

        Two triggers: (1) a config-update message on the pubsub network — a
        FULL rebuild, the event is authoritative; (2) the composite producer
        signature changing for reasons that don't ride a config topic (a
        pipeline starting / stopping).
        """
        self._refresh_config_subscriptions()
        config_changed = self._drain_config_updates()

        current = self._relay.composition
        if current is not None and not config_changed:
            signature = signature_of(self._build_stream_context())
            if signature == signature_of(current.context):
                return
        composition = self._compose_current()
        self._relay.set_composition(composition)
        await self._emit_replace_kinds(composition)

    def _current_camera_ids(self) -> tuple[str, ...]:
        """The sorted camera IDs across all live realtime pipelines."""
        ids: set[str] = set()
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                ids.update(pipeline.camera_ids)
        return tuple(sorted(ids))

    def _camera_image_sizes(self) -> dict[str, tuple[int, int]]:
        """Per-camera capture-resolution image size (width, height) in px.

        The coordinate space of the OVERLAY_2D values; the camera_layout message carries it so
        consumers can scale overlay points to their own display size. Sourced
        from the live pipelines' camera configs (rotation-aware width/height).
        """
        sizes: dict[str, tuple[int, int]] = {}
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            if not pipeline.alive:
                continue
            for camera_id in pipeline.camera_ids:
                config = pipeline.camera_configs[camera_id]
                sizes[camera_id] = (int(config.width), int(config.height))
        return sizes

    def _current_detector_type(self) -> str:
        """The configured detector type from the live realtime pipelines.

        One pipeline per camera set today; the frame's tracker keypoint names
        come from the first live pipeline's config. Defaults to ``rtmpose``
        (the config default) when no pipeline is running yet — the replace-kinds
        re-emit when the type changes.
        """
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                return pipeline.config.camera_node_config.detector_type
        return "rtmpose"

    # ── Frame source (wired to the app) ─────────────────────────────────

    async def _await_next_frame(self) -> "FrameContext | None":
        """Wait for the next frame, then compose its FrameContext.

        One frame message per frame carries images + overlays + reconstruction
        together — while a pipeline is live the source waits for the NEXT
        aggregator output (lockstep, newest-wins); with no pipeline it serves
        camera images directly (the frame's image field).
        """
        await self._app.wait_for_realtime_result(timeout=0.5)

        if not self._app.realtime_pipeline_manager.pipelines:
            return await self._await_camera_only_frame()

        outputs = self._app.get_latest_aggregator_outputs(
            if_newer_than=self._relay.last_sent_frame_number,
        )
        if not outputs:
            # Pipeline live but no new solver output — keep waiting; the
            # frame message must carry the frame's pose and image together.
            return None
        newest = max(outputs, key=lambda m: m.frame_number)

        await self._ensure_composition()

        image_bytes: bytearray | None = None
        mf_timestamp: float = 0.0
        pipeline = self._app.realtime_pipeline_manager.pipelines.get(newest.pipeline_id)
        if pipeline is not None:
            payload = pipeline.camera_group.get_frontend_payload_by_frame_number(
                frame_number=newest.frame_number,
                display_image_sizes=self._display_image_sizes,
            )
            if payload is not None:
                image_bytes, mf_timestamp = payload

        self._record_framerate(
            camera_group_id=newest.camera_group_id,
            frame_number=newest.frame_number,
        )
        await self._send_framerate_updates()

        if image_bytes is None:
            # A live pipeline frame with no camera-group payload is an
            # anomaly — surface it rather than silently shipping a frame message
            # without its image.
            logger.warning(
                f"camera-group payload unavailable for aggregator frame "
                f"{newest.frame_number} — frame message sent without its image"
            )

        return FrameContext(
            frame_number=newest.frame_number,
            timestamp=float(mf_timestamp),
            aggregator_output=newest,
            image_payload=bytes(image_bytes) if image_bytes is not None else None,
        )

    async def _await_camera_only_frame(self) -> "FrameContext | None":
        """Camera-only mode (no realtime pipeline): serve camera images.

        Each frame message carries just the
        newest camera-group payload.
        """
        await self._ensure_composition()
        payloads: dict[
            CameraGroupIdString, tuple[FrameNumberInt, float, bytearray]
        ] = self._app.camera_group_manager.get_latest_frontend_payloads(
            if_newer_than=self._relay.last_sent_frame_number,
            display_image_sizes=self._display_image_sizes,
        )
        if not payloads:
            return None
        group_id, (frame_number, mf_timestamp, image_bytes) = max(
            payloads.items(), key=lambda item: item[1][0]
        )
        self._record_framerate(
            camera_group_id=group_id,
            frame_number=frame_number,
        )
        await self._send_framerate_updates()
        return FrameContext(
            frame_number=int(frame_number),
            timestamp=float(mf_timestamp),
            image_payload=bytes(image_bytes),
        )

    async def __aenter__(self):
        logger.debug("Entering WebsocketRunner context manager...")
        self._websocket_should_continue = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketRunner context manager exiting...")
        self._websocket_should_continue = False
        if self.websocket.client_state == WebSocketState.CONNECTED:
            try:
                await self.websocket.close()
            except RuntimeError:
                pass
        for task in self.ws_tasks:
            if not task.done():
                task.cancel()
        logger.debug("WebsocketRunner context manager exited.")

    @property
    def should_continue(self):
        return (
            not self._global_kill_flag.value
            and self._websocket_should_continue
            and self.websocket.client_state == WebSocketState.CONNECTED
        )

    async def run(self):
        logger.info("Starting websocket runner...")
        # Replace-kinds first, on connect.
        composition = self._relay.composition
        if composition is not None:
            await self._emit_replace_kinds(composition)
        self.ws_tasks = [
            asyncio.create_task(self._relay.run(), name="WebsocketMessageRelay"),
            asyncio.create_task(self._logs_relay(), name="WebsocketLogsRelay"),
            asyncio.create_task(self._client_message_handler(), name="WebsocketClientMessageHandler"),
            asyncio.create_task(self._app_state_sender(), name="WebsocketAppStateSender"),
            asyncio.create_task(self._posthoc_progress_sender(), name="WebsocketPosthocProgressSender"),
        ]

        try:
            await asyncio.gather(*self.ws_tasks)
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            # A fatal runner error must stop the whole app — if it only kills
            # this connection, the frontend reconnects into the same crash
            # forever.
            self._websocket_should_continue = False
            self._global_kill_flag.value = True
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()
            raise

    async def _app_state_sender(self):
        logger.info("Starting app-state sender task...")
        previous_state: dict | None = None
        try:
            while self.should_continue:
                state_dict = self._app.to_state_dict()
                if previous_state is None or state_dict != previous_state:
                    message = AppStateMessage.from_state_dict(
                        server_pid=os.getpid(), state=state_dict
                    )
                    await self._serializer.send_message(encode_message(message))
                await asyncio.sleep(1.0)
                previous_state = state_dict
        except asyncio.CancelledError:
            pass
        except WebSocketDisconnect:
            logger.info("Client disconnected, ending app-state sender task...")
        except Exception as e:
            logger.exception(f"Error in app-state sender: {e.__class__}: {e}")
            self._websocket_should_continue = False
            self._global_kill_flag.value = True
            raise

    async def _posthoc_progress_sender(self):
        """Drain posthoc pipeline progress and forward it to the client.

        The posthoc pipelines publish progress into per-pipeline
        subscriptions; this task is the single drainer that moves them onto
        the websocket as ``posthoc_progress`` messages (the frontend's
        progress panel consumes these). The manager's queue is drained each
        tick — a progress message is never lost, and the sender idles when
        there is nothing to forward.
        """
        logger.info("Starting posthoc-progress sender task...")
        try:
            while self.should_continue:
                updates = self._app.posthoc_pipeline_manager.get_progress_updates()
                updates.extend(
                    self._app.posthoc_pipeline_manager.evict_completed()
                )
                for update in updates:
                    message = ProgressMessage.from_pipeline_progress(update)
                    await self._serializer.send_message(encode_message(message))
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        except WebSocketDisconnect:
            logger.info("Client disconnected, ending posthoc-progress sender task...")
        except Exception as e:
            logger.exception(f"Error in posthoc-progress sender: {e.__class__}: {e}")
            self._websocket_should_continue = False
            self._global_kill_flag.value = True
            raise

    def _record_framerate(
        self,
        *,
        camera_group_id: CameraGroupIdString,
        frame_number: FrameNumberInt,
    ) -> None:
        """Record the server-side frame cadence.

        ``ServerFramerateCalculator`` derives per-frame durations from
        consecutive timestamps — its documented input is ``perf_counter_ns``
        at grab time, so the record uses the local monotonic clock. (Passing
        the capture timestamp is wrong: its 0.0/None case produces
        non-positive durations and the calculator raises.)
        """
        if camera_group_id not in self._server_framerate_calculators:
            self._server_framerate_calculators[camera_group_id] = ServerFramerateCalculator(
                source_name="Server")
        self._server_framerate_calculators[camera_group_id].update(
            frame_number=frame_number,
            # float(): skellycam's signature types this as float; perf_counter_ns
            # returns int.
            capture_timestamp_ns=float(time.perf_counter_ns()),
        )
        if camera_group_id not in self._display_framerate_trackers:
            self._display_framerate_trackers[camera_group_id] = FramerateTracker.create(
                framerate_source="Display")
        self._display_framerate_trackers[camera_group_id].update(time.perf_counter_ns())

    async def _send_framerate_updates(self) -> None:
        now = time.perf_counter()
        if now - self._last_framerate_send_time < 0.25:
            return
        for camera_group_id, server_calc in self._server_framerate_calculators.items():
            if camera_group_id not in self._display_framerate_trackers:
                continue
            server_framerate = server_calc.current_framerate
            display_tracker = self._display_framerate_trackers[camera_group_id]
            if server_framerate and display_tracker.has_data:
                message = FramerateMessage(
                    camera_group_id=camera_group_id,
                    backend_framerate=DetailedFramerate.from_current_framerate(server_framerate),
                    frontend_framerate=DetailedFramerate.from_current_framerate(display_tracker.current_framerate),
                )
                await self._serializer.send_message(encode_message(message))
                server_calc.clear()
                display_tracker.clear()
        self._last_framerate_send_time = now

    async def _logs_relay(self, ws_log_level: int = int(MIN_LOG_LEVEL_FOR_WEBSOCKET)):
        logger.info("Starting websocket log relay listener...")
        logs_queue = get_websocket_log_queue()
        try:
            while self.should_continue:
                if self.websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        log_entry: dict = logs_queue.get_nowait()
                    except Empty:
                        await await_10ms()
                        continue
                    except (EOFError, OSError):
                        continue
                    if not isinstance(log_entry, dict):
                        continue
                    if log_entry.get("levelno", 0) < ws_log_level:
                        continue
                    message = LogMessage(record=LogRecord.from_logging_dict(log_entry))
                    await self._serializer.send_message(encode_message(message))
                else:
                    await await_10ms()
        except asyncio.CancelledError:
            logger.debug("Log relay task cancelled")
        except WebSocketDisconnect:
            logger.info("Client disconnected, ending log relay task...")
        except Exception as e:
            logger.exception(
                f"Error in websocket log relay: {e.__class__.__name__}: {e or '(no message)'} "
                f"— ws state: {self.websocket.client_state}"
            )
            self._websocket_should_continue = False
            self._global_kill_flag.value = True
            raise

    async def _client_message_handler(self):
        """Handle messages from the client, including settings messages."""
        logger.info("Starting client message handler...")
        try:
            while self.should_continue:
                message = await self.websocket.receive()
                if message:
                    msg_type = message.get("type", "")

                    if msg_type == "websocket.disconnect":
                        logger.info(f"Received websocket disconnect (code={message.get('code', 'unknown')})")
                        self._websocket_should_continue = False
                        break

                    if "text" in message:
                        text_content = message.get("text", "")
                        if text_content.strip().startswith("{") or text_content.strip().startswith("["):
                            try:
                                data = json.loads(text_content)

                                if "frameNumber" in data:
                                    # The ack's only remaining role: display image
                                    # sizes, which drive SkellyCam's JPEG downscaling.
                                    raw_sizes = data.get("displayImageSizes", None)
                                    if raw_sizes is not None:
                                        parsed = {
                                            cam_id: {k: float(v) for k, v in dims.items()}
                                            for cam_id, dims in raw_sizes.items()
                                        }
                                        self._display_image_sizes = {
                                            cam_id: dims
                                            for cam_id, dims in parsed.items()
                                            if dims.get("width", 0) > 0 and dims.get("height", 0) > 0
                                        } or None
                                    else:
                                        self._display_image_sizes = None
                                else:
                                    logger.debug(f"Received unhandled JSON message: {list(data.keys())}")

                            except json.JSONDecodeError as e:
                                raise ValueError(f"Failed to decode JSON message: {e}") from e
                        else:
                            if text_content.startswith("ping"):
                                await self._serializer.send_raw_text("pong")
                            elif text_content.startswith("pong"):
                                pass
                            else:
                                logger.info(f"Websocket received message: `{text_content}`")
                    elif "bytes" in message:
                        logger.trace(f"Received binary websocket message ({len(message['bytes'])} bytes)")
                    else:
                        raise RuntimeError(f"Received unexpected message format: {message}")

        except asyncio.CancelledError:
            logger.debug("Client message handler task cancelled")
        except Exception as e:
            logger.exception(f"Error handling client message: {e.__class__}: {e}")
            self._websocket_should_continue = False
            self._global_kill_flag.value = True
            raise
        finally:
            logger.info("Ending client message handler...")
