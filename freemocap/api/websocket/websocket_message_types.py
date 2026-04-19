import enum


class WebsocketMessageType(str, enum.Enum):
    """All JSON message types sent over the freemocap websocket.

    Inherits from str so it serializes to its string value in JSON automatically.
    """
    FRONTEND_PAYLOAD = "frontend_payload"
    FRAMERATE_UPDATE = "framerate_update"
    POSTHOC_PROGRESS = "posthoc_progress"
    LOG_RECORD = "log_record"
    TRACKER_SCHEMAS = "tracker_schemas"
