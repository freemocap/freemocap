import logging

import requests

logger = logging.getLogger(__name__)

def send_pipedream_ping():
    logger.info("sending anonymous ping to pipedream to let the devs know that someone is using this, which will allow us to secure more funding to support this project")
    r = requests.post('https://eoivu13g86if0cp.m.pipedream.net', files={})
