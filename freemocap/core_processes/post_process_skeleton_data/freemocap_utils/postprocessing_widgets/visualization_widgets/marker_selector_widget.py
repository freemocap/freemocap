
from freemocap_utils.postprocessing_widgets.visualization_widgets.mediapipe_skeleton_builder import mediapipe_indices

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QComboBox
from PyQt6.QtCore import pyqtSignal


class MarkerSelectorWidget(QWidget):
    marker_to_plot_updated_signal = pyqtSignal()
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        
        combo_box_items = mediapipe_indices
        # combo_box_items.insert(0,'')
        self.marker_combo_box = QComboBox()
        self.marker_combo_box.addItems(combo_box_items)
        self.marker_combo_box.addItems(['center of mass'])
        self._layout.addWidget(self.marker_combo_box)

        self.current_marker = self.marker_combo_box.currentText()
        self.marker_combo_box.currentTextChanged.connect(self.return_marker)

    def return_marker(self):
        self.current_marker = self.marker_combo_box.currentText()
        self.marker_to_plot_updated_signal.emit()

        return self.current_marker


