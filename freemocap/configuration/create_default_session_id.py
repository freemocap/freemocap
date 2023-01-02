from datetime import time


def create_default_session_id(string_tag: str = None):
    session_id = "session_" + time.strftime("%Y-%m-%d-%H_%M_%S")

    if string_tag is not None:
        session_id = session_id + "_" + string_tag

    return session_id
