import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_path_to_sample_data():
    sample_data_path = Path().home() / "freemocap_data" / "recording_sessions" / "freemocap_sample_data"
    sample_data_path = sample_data_path.resolve()
    if not sample_data_path.exists():
        logger.error(
            "Sample data not found. To download sample data, in the main FreeMoCap Gui:"
            " `File Menu`>>'Download Sample Data',"
            " then press the `Process Recording Folder` button in the `Process Data` tab")
        raise Exception(f"Could not find sample data at {sample_data_path}")

    output_data_path = sample_data_path / "output_data"
    if not output_data_path.exists():
        logger.error(
            f"Sample data found at `{sample_data_path}, but has not been processed yet. "
            f"To process sample data, go to the main FreeMoCap Gui, "
            f"select the sample data folder and click the 'Process Videos' button or whatever its called lol")
        raise Exception(f"Could not find processed sample data at {output_data_path}")

    return sample_data_path


if __name__ == "__main__":
    sample_data_path = get_path_to_sample_data()
    print(f"Sample data downloaded found at: {str(sample_data_path)}")
