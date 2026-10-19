from unittest.mock import patch

import cbor2
import pytest

from freemocap.core.streaming.message_model import AppStateMessage, encode_message
from freemocap.system.tracker_capabilities import mediapipe_unavailable_reason


@pytest.mark.parametrize('system,machine,installed,expected', [
    ('darwin', 'x86_64', False, 'Intel Macs'),
    ('darwin', 'x86_64', True, 'Intel Macs'),
    ('darwin', 'arm64', True, None),
    ('win32', 'AMD64', True, None),
    ('linux', 'x86_64', False, 'not installed'),
])
def test_backend_reports_tracker_availability(system, machine, installed, expected):
    with patch('freemocap.system.tracker_capabilities.sys.platform', system), \
         patch('freemocap.system.tracker_capabilities.platform.machine', return_value=machine), \
         patch('freemocap.system.tracker_capabilities.importlib.util.find_spec', return_value=object() if installed else None):
        reason = mediapipe_unavailable_reason()
        if expected is None:
            assert reason is None
        else:
            assert expected in reason
        message = AppStateMessage.from_state_dict(server_pid=123, state={})
        assert cbor2.loads(encode_message(message)).get('mediapipe_unavailable_reason') == reason
