import socket

PROTOCOL = "http"
HOSTNAME = "localhost"
PREFERRED_PORT = 53117
MAX_PORT_ATTEMPTS = 50
PORT_SENTINEL = "FREEMOCAP_PORT"


def find_available_port(*, hostname: str = HOSTNAME, preferred_port: int = PREFERRED_PORT, max_attempts: int = MAX_PORT_ATTEMPTS) -> int:
    """Try to bind to the preferred port, incrementing upward until one is available."""
    for offset in range(max_attempts):
        port = preferred_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((hostname, port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"Could not find an available port in range {preferred_port}-{preferred_port + max_attempts - 1}"
    )


def format_port_sentinel(*, port: int) -> str:
    """Format the stdout line that Electron parses to discover the port."""
    return f"{PORT_SENTINEL}={port}"