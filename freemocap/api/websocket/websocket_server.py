"""
WebSocket server — the per-connection supervisor of the self-describing message
stream.

Thin supervisor for one WebSocket connection: composes the message send path
(SendSerializer + FrameRelay) with the log relay, the app-state sender, the
posthoc-progress sender, and the inbound client-message handler (display sizes). The FrameRelay
is the ONE consumer of the pipeline's aggregator output; the camera images ride
each frame message's image field. Flow control is newest-wins — there is no ack
window; the inbound frameAcknowledgment carries displayImageSizes only (they
drive SkellyCam's JPEG downscaling).

The frame message is fully self-contained: convention, calibrated cameras,
model definitions, instances, trackers, and the image all ride every frame. The
composition is rebuilt only when the data model or calibration changes
(pipeline start/stop, detector, camera set, calibration hot-reload).
"""
import asyncio
import json
import logging
import os
import time
from queue import Empty

from fastapi import FastAPI
from skellycam.api.websocket.websocket_server import ServerFramerateCalculator
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate
from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt
from skellycam.core.camera.config.image_rotation_types import RotationTypes
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellylogs import get_websocket_log_queue
from skellylogs.handlers.websocket_log_queue_handler import MIN_LOG_LEVEL_FOR_WEBSOCKET
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from freemocap.api.websocket.frame_relay import FrameRelay
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.app.freemocap_application import FreemocapApplication, get_freemocap_app
from freemocap.core.pipeline.realtime.camera_node_config import DEFAULT_DETECTOR_TYPE
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.skeletons.tracked_skeleton_set import build_tracked_skeletons
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.message_model import (
    AppStateMessage,
    CalibratedCamera,
    CameraRotation,
    DetailedFramerate,
    FramerateMessage,
    LogMessage,
    LogRecord,
    ProgressMessage,
    encode_message,
)
from freemocap.core.streaming.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.utilities.wait_functions import await_10ms

logger = logging.getLogger(__name__)


_CAMERA_ROTATION_BY_CONFIG = {
    RotationTypes.NO_ROTATION: CameraRotation.NONE,
    RotationTypes.CLOCKWISE_90: CameraRotation.CLOCKWISE_90,
    RotationTypes.ROTATE_180: CameraRotation.ROTATE_180,
    RotationTypes.COUNTERCLOCKWISE_90: CameraRotation.COUNTERCLOCKWISE_90,
}


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
        # Calibration hot-reload source (feeds the frame's cameras field).
        self._calibration_state = CalibrationStateTracker.create_and_try_load()
        # The skeleton set, memoized on the config it is built from. Constructing one loads
        # several YAMLs off disk, and the composition check runs on every emitted frame.
        self._tracked_skeletons_cache: tuple[tuple, tuple] | None = None
        # The relay consumes raw frame contexts via the injected source.
        self._relay = FrameRelay(
            serializer=self._serializer,
            source=self._await_next_frame,
            should_continue=lambda: self.should_continue,
        )
        # The initial composition (may be image-only — rebuilt when the data
        # model changes, e.g. a pipeline starts).
        self._relay.set_composition(self._compose_current())

    # ── Composition lifecycle ──────────────────────────────────────────

    def _build_stream_context(self) -> StreamContext:
        camera_ids = self._current_camera_ids()
        detector_type = self._current_detector_type()
        return StreamContext(
            # Every skeleton the stream describes. Rebuilt with the context, so a detector
            # change re-derives which landmarks each skeleton measures.
            skeletons=self._tracked_skeletons(),
            camera_ids=camera_ids,
            calibrated_cameras=self._calibrated_cameras(),
            detector_type=detector_type,
            pipeline_live=bool(camera_ids),
            live_image_sizes={
                cam_id: (config.width, config.height)
                for cam_id, config in self._live_camera_configs().items()
            },
        )

    def _compose_current(self):
        return compose_messages(self._build_stream_context())

    async def _ensure_composition(self) -> None:
        """Rebuild the composition when the data model or calibration changed.

        The calibration hot-reloads on a file-mtime check; the data model is a
        simple signature (camera set, detector type, pipeline liveness, and the
        resolved calibrated cameras). The frame message is self-contained, so a
        rebuild just swaps the composition — nothing is re-emitted separately.

        This runs on EVERY emitted frame, so the signature is computed from its raw
        sources and compared BEFORE anything is built. Building the context first and
        checking afterwards costs a full skeleton construction per frame — six YAML loads
        and a 61-segment rebuild — which does not show up in the camera framerate at all,
        only in the rate frames actually reach the client.
        """
        self._calibration_state.check_for_update()
        current = self._relay.composition
        if current is not None and self._live_context_signature() == self._context_signature(current.context):
            return
        self._relay.set_composition(compose_messages(self._build_stream_context()))

    def _live_context_signature(self) -> tuple:
        """The context signature, read straight from its sources.

        Must stay identical to `_context_signature`; it exists so the per-frame check does
        not have to construct a `StreamContext` (and therefore the skeletons) to run.
        """
        camera_ids = self._current_camera_ids()
        return (
            camera_ids,
            self._current_detector_type(),
            bool(camera_ids),
            self._calibrated_cameras(),
        )

    def _calibrated_cameras(self) -> tuple[CalibratedCamera, ...]:
        """The current calibration's cameras, merged with the live camera config's

        rotation + rotated image size. The overlay points and the JPEG both live in
        the rotated image space, so their dimensions must come from the LIVE camera
        config (which owns the rotation), not the stale calibration recording."""
        calibration = self._calibration_state.calibration
        if calibration is None:
            return ()
        configs = self._live_camera_configs()
        calibration_by_id = {cm.id: cm for cm in calibration.cameras}
        calibration_by_index = {cm.index: cm for cm in calibration.cameras}
        cameras = []
        index_matched_ids: list[str] = []
        for live_id, config in configs.items():
            # Match the calibration camera by id; fall back to its index when the
            # camera was re-enumerated and its id drifted (e.g. d441 -> fa5a).
            # The fallback is LOUD: pairing one camera's intrinsics with another
            # id is only tolerable while everyone can see that it happened.
            camera_model = calibration_by_id.get(live_id)
            if camera_model is None:
                camera_model = calibration_by_index.get(config.camera_index)
                if camera_model is not None:
                    index_matched_ids.append(
                        f"{live_id} -> index {config.camera_index} "
                        f"(calibration id {camera_model.id!r})"
                    )
            if camera_model is None:
                continue
            rotation = _CAMERA_ROTATION_BY_CONFIG.get(config.rotation, CameraRotation.NONE)
            # config.width / config.height are ALREADY the rotated dimensions
            # (CameraConfig.width/height swap for PORTRAIT orientation).
            cameras.append(
                CalibratedCamera.from_camera_model(
                    camera_model,
                    camera_id=live_id,
                    rotation=rotation,
                    image_size=(config.width, config.height),
                )
            )
        if index_matched_ids:
            logger.error(
                "Calibration cameras matched by INDEX, not id - the camera ids "
                "drifted from the calibration recording and its intrinsics may "
                "belong to a different physical camera. Recalibrate to fix: %s",
                "; ".join(index_matched_ids),
            )
        return tuple(cameras)

    def _live_camera_configs(self) -> CameraConfigs:
        """The live camera configs (keyed by camera id) across every alive realtime

        pipeline — the source of the rotation + rotated image size."""
        configs: CameraConfigs = {}
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                configs.update(pipeline.camera_configs)
        return configs

    @staticmethod
    def _context_signature(ctx: StreamContext) -> tuple:
        return (ctx.camera_ids, ctx.detector_type, ctx.pipeline_live, ctx.calibrated_cameras)

    def _current_camera_ids(self) -> tuple[str, ...]:
        """The sorted camera IDs across all live realtime pipelines."""
        ids: set[str] = set()
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                ids.update(pipeline.camera_ids)
        return tuple(sorted(ids))

    def _tracked_skeletons(self) -> tuple:
        """Every skeleton the stream describes, from the live pipeline's own config.

        Read from the SAME place the aggregator reads it, so the frame's models and its
        instances cannot come from different opinions about what is being tracked.

        Memoized on the config it is derived from. Building a skeleton set means loading
        the skeleton, rest-pose, mapping, centre-of-mass and anthropometry YAMLs off disk;
        it is a pure function of that config, so it is built when the config changes and
        not once per caller.
        """
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                return self._skeletons_for(
                    camera_node_config=pipeline.config.camera_node_config,
                    scale_window_frames=(
                        pipeline.config.aggregator_config.realtime_filter_config.segment_scale_window_frames
                    ),
                )
        # No pipeline yet: describe what the defaults would track, so a client connecting
        # early still receives a coherent model list.
        return self._skeletons_for(
            camera_node_config=CameraNodeConfig(),
            scale_window_frames=RealtimeFilterConfig().segment_scale_window_frames,
        )

    def _skeletons_for(
            self,
            *,
            camera_node_config: CameraNodeConfig,
            scale_window_frames: int,
    ) -> tuple:
        cache_key = (camera_node_config.model_dump_json(), scale_window_frames)
        cached = self._tracked_skeletons_cache
        if cached is not None and cached[0] == cache_key:
            return cached[1]
        skeletons = build_tracked_skeletons(
            camera_node_config=camera_node_config,
            scale_window_frames=scale_window_frames,
        )
        self._tracked_skeletons_cache = (cache_key, skeletons)
        return skeletons

    def _current_detector_type(self) -> str:
        """The configured detector type from the live realtime pipelines.

        One pipeline per camera set today; the frame's tracker keypoint names
        come from the first live pipeline's config. Defaults to the config
        default when no pipeline is running yet — the replace-kinds re-emit
        when the type changes.
        """
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                return pipeline.config.camera_node_config.detector_type
        return DEFAULT_DETECTOR_TYPE

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

        image_bytes: bytes | bytearray | memoryview | None = None
        mf_timestamp: float = 0.0
        pipeline = self._app.realtime_pipeline_manager.pipelines.get(newest.pipeline_id)
        if pipeline is not None:
            # JPEG resize+encode of every camera is milliseconds of CPU work —
            # run it off the event loop so the frame sender, log relay, and
            # framerate relays don't stall behind it each frame.
            payload = await asyncio.to_thread(
                pipeline.camera_group.get_frontend_payload_by_frame_number,
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
            image_payload=image_bytes if image_bytes is not None else None,
        )

    async def _await_camera_only_frame(self) -> "FrameContext | None":
        """Camera-only mode (no realtime pipeline): serve camera images.

        Each frame message carries just the
        newest camera-group payload.
        """
        await self._ensure_composition()
        payloads: dict[
            CameraGroupIdString, tuple[FrameNumberInt, float, bytes | bytearray | memoryview]
        ] = await asyncio.to_thread(
            self._app.camera_group_manager.get_latest_frontend_payloads,
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
            image_payload=image_bytes,
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
                    except (EOFError, OSError) as error:
                        # The queue itself is failing - back off and log rather
                        # than spin on it inside the event loop.
                        logger.error(
                            "Log queue read failed (%s: %s); backing off 100ms",
                            error.__class__.__name__,
                            error,
                        )
                        self._websocket_should_continue = False
                        self._global_kill_flag.value = True
                        raise
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
