import logging
import uuid

import requests

logger = logging.getLogger(__name__)


class PipedreamPings:
    def __init__(
        self,
    ):
        self._pipedream_url = "https://eowipinr6rcpbo0.m.pipedream.net"
        self._pings_dict = {}
        self.update_pings_dict(key="session_uuid", value=str(uuid.uuid4()))

    def update_pings_dict(self, key, value):
        self._pings_dict[key] = value

    def send_pipedream_ping(self):
        logger.info(
            f"Sending anonymous ping to pipedream to let the devs know that someone is using this, which will allow "
            f"us to secure more funding to support this project. This is the dictionary of info we're sending: \n "
            f"{self._pings_dict} "
        )

        try:
            requests.post(self._pipedream_url, json=self._pings_dict, timeout=(5, 60))
        except requests.RequestException:
            logger.error("Failed to send anonymous ping to pipedream")
