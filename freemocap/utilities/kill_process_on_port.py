import logging

import psutil

logger = logging.getLogger(__name__)


def kill_process_on_port(port: int):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == port:
                    logger.warning(
                        f"Process already running on port: {port}, shutting it down...[TODO - HANDLE THIS BETTER! Figure out why we're leaving behind zombie processes...]")
                    proc.kill()
                    logger.warning(f"Killed process {proc.info['name']} (PID: {proc.info['pid']}) on port {port}")
                    return
        except psutil.AccessDenied:
            continue


if __name__ == "__main__":
    from skellycam.api.server.server_constants import PORT

    kill_process_on_port(PORT)
