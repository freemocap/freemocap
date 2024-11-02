from pathlib import Path


def clean_path(path: str) -> str:
    """
    Replace the home directory with a tilde in the path
    """
    home_dir = str(Path.home())
    if home_dir in path:
        return path.replace(home_dir, "~")
    return path
