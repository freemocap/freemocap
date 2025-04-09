from pathlib import Path
from typing import Union, List
import re

from pathlib import Path
from typing import Union, List


def get_video_paths(path_to_video_folder: Union[str, Path]) -> List[Path]:
    """Search the folder for 'mp4' files (case insensitive) and return them as a list"""

    list_of_video_paths = list(Path(path_to_video_folder).glob("*.mp4")) + list(
        Path(path_to_video_folder).glob("*.MP4")
    )
    unique_list_of_video_paths = get_unique_list(list_of_video_paths)
    return sorted(unique_list_of_video_paths, key=lambda p: str(p).lower())



def get_unique_list(list: list) -> list:
    """Return a list of the unique elements from input list"""
    unique_list = []
    [unique_list.append(element) for element in list if element not in unique_list]

    return unique_list


# def numeric_sort_key(path: Path):
#     """Extracts numbers from filename for natural sorting"""
#     numbers = re.findall(r'\d+', path.name)
#     return [int(num) for num in numbers] if numbers else [float('inf')]