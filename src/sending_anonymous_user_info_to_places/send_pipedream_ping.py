import logging

import requests

logger = logging.getLogger(__name__)


def send_pipedream_ping(pipe_dream_ping_dictionary):
    logger.info(
        f"sending anonymous ping to pipedream to let the devs know that someone is using this, which will allow us to secure more funding to support this project. This is the dictionary of info we're sending: \n {pipe_dream_ping_dictionary}"
    )

    r = requests.post(
        "https://eoivu13g86if0cp.m.pipedream.net", json={"pinged_string": pipe_dream_ping_dictionary}
    )
