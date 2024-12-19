import multiprocessing


def get_process_name() -> str:
    return multiprocessing.current_process().name
