import pytest
from unittest.mock import patch
from pathlib import Path
from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import guess_blender_exe_path_from_path
from freemocap.core_processes.export_data.blender_stuff.get_best_guess_of_blender_path import get_best_guess_of_blender_path


def test_guess_blender_exe_with_existing_path():
    with patch.object(Path, 'glob', return_value=[Path('/fake/path/Blender'), Path('/fake/path/Blender2')]):
        result = guess_blender_exe_path_from_path(Path('/fake/path'))
        assert result == Path('/fake/path/Blender2/blender.exe')


def test_guess_blender_exe_with_no_blender_folder():
    with patch.object(Path, 'glob', return_value=[]):
        result = guess_blender_exe_path_from_path(Path('/fake/path'))
        assert result is None


@pytest.mark.parametrize("drive, expected", [
    ("/C", "\\C:\\Program Files\\Blender Foundation\\Blender\\blender.exe\\blender.exe"),
    ("/D", "\\D:\\Program Files\\Blender Foundation\\Blender\\blender.exe\\blender.exe"),
    ("/B", "\\B:\\Program Files\\Blender Foundation\\Blender\\blender.exe\\blender.exe"),
])
def test_blender_found_on_drive(drive, expected):
    with patch.object(Path, 'glob', return_value=[Path(f'{drive}:/Program Files/Blender Foundation/Blender/blender.exe')]), \
         patch.object(Path, 'is_file', return_value=True), \
         patch('platform.system', return_value="Windows"):
        result = get_best_guess_of_blender_path()
        assert result == expected


def test_blender_not_found():
    with patch.object(Path, 'glob', return_value=[]), \
         patch.object(Path, 'is_file', return_value=False):
        result = get_best_guess_of_blender_path()
        assert result is None
