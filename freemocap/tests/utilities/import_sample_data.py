import io
import requests
import zipfile
from pathlib import Path


def load_sample_data() -> Path:
    zip_file_url = "https://figshare.com/ndownloader/files/39369101"
    sample_session_name = "freemocap_sample_data"
    sample_session_zip = sample_session_name + ".zip"

    extract_to_path = Path.home() / "sample_freemocap_data"
    extract_to_path.mkdir(exist_ok=True)

    sample_session_path = extract_to_path / sample_session_name

    if not Path.exists(sample_session_path):
        r = requests.get(zip_file_url)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(extract_to_path)

    return sample_session_path


def find_data_folder_path(session_folder_path: Path) -> Path:
    for subfolder_path in session_folder_path.iterdir():

        if subfolder_path.name == "DataArrays":
            return subfolder_path
        if subfolder_path.name == "output_data":
            return subfolder_path

    raise Exception(f"Could not find a data folder in path {str(session_folder_path)}")


def find_synchronized_videos_folder_path(session_folder_path: Path) -> Path:
    for subfolder_path in session_folder_path.iterdir():

        if subfolder_path.name == "synchronized_videos":
            return subfolder_path

        if subfolder_path.name == "SyncedVideos":
            return subfolder_path

    raise Exception(f"Could not find a videos folder in path {str(session_folder_path)}")


def find_skeleton_npy_file_name(data_folder_name: Path) -> Path:
    npy_path_list = [path.name for path in data_folder_name.glob("*.npy")]

    if "mediapipe_body_3d_xyz.npy" in npy_path_list:
        return data_folder_name / "mediapipe_body_3d_xyz.npy"

    if "mediaPipeSkel_3d_origin_aligned.npy" in npy_path_list:
        return data_folder_name / "mediaPipeSkel_3d_origin_aligned.npy"

    raise Exception(f"Could not find a skeleton NPY file in path {str(data_folder_name)}")


def find_total_body_center_of_mass_file_name(data_folder_name: Path) -> Path:
    npy_path_list = [path.name for path in data_folder_name.glob("*.npy")]

    center_of_mass_subfolder_path = data_folder_name / "center_of_mass"
    if center_of_mass_subfolder_path.exists:
        raw_data_npy_path_list = [path.name for path in center_of_mass_subfolder_path.glob("*.npy")]

        if "total_body_center_of_mass_xyz.npy" in raw_data_npy_path_list:
            return center_of_mass_subfolder_path / "total_body_center_of_mass_xyz.npy"

    if "totalBodyCOM_frame_XYZ.npy" in npy_path_list:
        return data_folder_name / "totalBodyCOM_frame_XYZ.npy"

    raise Exception(f"Could not find a total body center of mass npy file in path {str(data_folder_name)}")


def find_2d_data_file_name(data_folder_name: Path) -> Path:
    npy_path_list = [path.name for path in data_folder_name.glob("*.npy")]

    raw_data_subfolder_path = data_folder_name / "raw_data"
    if raw_data_subfolder_path.exists:
        raw_data_npy_path_list = [path.name for path in raw_data_subfolder_path.glob("*.npy")]

        if "mediapipe2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy" in raw_data_npy_path_list:
            return raw_data_subfolder_path / "mediapipe2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy"

    if "mediaPipeData_2d.npy" in npy_path_list:
        return data_folder_name / "mediaPipeData_2d.npy"

    raise Exception(f"Could not find a 2d data file in path {str(data_folder_name)}")


def find_reprojection_error_file_name(data_folder_name: Path) -> Path:
    npy_path_list = [path.name for path in data_folder_name.glob("*.npy")]

    raw_data_subfolder_path = data_folder_name / "raw_data"
    if raw_data_subfolder_path.exists:
        raw_data_npy_path_list = [path.name for path in raw_data_subfolder_path.glob("*.npy")]

        if "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy" in raw_data_npy_path_list:
            return raw_data_subfolder_path / "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy"

    if "mediaPipeSkel_reprojErr.npy" in npy_path_list:
        return data_folder_name / "mediaPipeSkel_reprojErr.npy"

    raise Exception(f"Could not find reprojection error data file in path {str(data_folder_name)}")


if __name__ == "__main__":
    sample_data_path = load_sample_data()
