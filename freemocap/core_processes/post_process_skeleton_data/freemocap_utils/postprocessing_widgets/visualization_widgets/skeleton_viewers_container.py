from PyQt6.QtWidgets import QWidget, QHBoxLayout
from freemocap_utils.postprocessing_widgets.visualization_widgets.skeleton_view_widget import SkeletonViewWidget


class SkeletonViewersContainer(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()

        self.raw_skeleton_viewer = SkeletonViewWidget('Raw data')
        layout.addWidget(self.raw_skeleton_viewer)

        self.processed_skeleton_viewer = SkeletonViewWidget('Post-processed data')
        layout.addWidget(self.processed_skeleton_viewer)

        self.setLayout(layout)

    def plot_raw_skeleton(self, raw_skeleton_data):
        self.raw_skeleton_viewer.load_skeleton(raw_skeleton_data)

    def plot_processed_skeleton(self, processed_skeleton_data):
        self.processed_skeleton_viewer.load_skeleton(processed_skeleton_data)

    def update_raw_viewer_plot(self, frame_number):
        self.raw_skeleton_viewer.replot(frame_number)

    def update_processed_viewer_plot(self, frame_number):
        if self.processed_skeleton_viewer.skeleton_loaded:
            self.processed_skeleton_viewer.replot(frame_number)