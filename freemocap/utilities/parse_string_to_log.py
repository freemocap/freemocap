import logging

logger = logging.getLogger(__name__)

def parse_string_to_log(log_string: str) -> None:
    split_string = log_string.split(":", maxsplit=1)
    prefix = split_string[0]
    if len(split_string) == 1: # Log as debug if there is no colon
        logger.debug(prefix)
        return
    else:
        prefix = prefix.upper()
        message = split_string[1].strip()

    print(f"prefix: {prefix}")

    if prefix == "DEBUG":
        logger.debug(message)
    elif prefix == "INFO":
        logger.info(message)
    elif prefix == "WARNING":
        logger.warning(message)
    elif prefix == "ERROR":
        logger.error(message)
    elif prefix == "CRITICAL":
        logger.critical(message)
    else:
        logger.debug(message)