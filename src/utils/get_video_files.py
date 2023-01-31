from pathlib import Path

def get_video_files(path_to_video_folder: Path) -> list:
    '''Search the folder for 'mp4' files (case insensitive) and return a list of their paths'''

    list_of_video_paths = list(Path(path_to_video_folder).glob("*.mp4")) + list(Path(path_to_video_folder).glob("*.MP4"))
    unique_list_of_video_paths = get_unique_list(list_of_video_paths)

    return unique_list_of_video_paths

def get_unique_list(list: list) -> list:
    '''Return a list of the unique elements from input list'''
    unique_list = []
    [unique_list.append(clip) for clip in list if clip not in unique_list]

    return unique_list