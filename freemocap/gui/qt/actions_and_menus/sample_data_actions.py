from PySide6.QtGui import QAction
from freemocap.utilities.download_sample_data import DATASETS


class DatasetDownloadAction(QAction):
    """
    Action with built-in trigger to download a specific dataset.
    """

    def __init__(self, menu_label: str, dataset_name: str, freemocap_main_window):
        super().__init__(menu_label, freemocap_main_window)
        self.triggered.connect(lambda: freemocap_main_window.download_data(dataset_name))


def make_download_data_action(
    dataset_key: str,
    freemocap_main_window,
) -> DatasetDownloadAction:
    """
    Makes a DatasetDownloadAction for the specified dataset key.
    Raises ValueError if the dataset key is not recognized.
    """
    if dataset_key not in DATASETS:
        raise ValueError(f"Unknown dataset '{dataset_key}'. Options: {list(DATASETS)}")

    dataset = DATASETS[dataset_key]

    return DatasetDownloadAction(
        menu_label=dataset.menu_label, dataset_name=dataset_key, freemocap_main_window=freemocap_main_window
    )
