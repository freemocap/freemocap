from PyQt6.QtCore import Qt, QPointF, QRect
from PyQt6.QtGui import QPainter, QColor, QBrush, QLinearGradient, QPen
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from freemocap_utils.postprocessing_widgets.stylesheet import label_stylesheet


class LEDIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(15, 15)
        self.color = QColor(156,0,0)

    def set_not_started_process_color(self):
        self.color = QColor(156,0,0)
        self.update()

    def set_in_process_color(self):
        self.color = QColor(255,230,0)
        self.update()

    def set_finished_process_color(self):
        self.color = QColor(0,108,154)
        self.update()

    def set_color(self, r,g,b):
        self.color = QColor(r,g,b)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        diameter = min(self.width(), self.height())

        # Create a gradient for the LED color
        gradient = QLinearGradient(QPointF(0, 0), QPointF(diameter, diameter))
        gradient.setColorAt(0, self.color.lighter(150))
        gradient.setColorAt(1, self.color.darker(150))

        # Paint the LED circle with the gradient
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(self.rect().center()), diameter / 2, diameter / 2)


        # Add a subtle border to the LED circle
        border_color = self.color.lighter(150)
        border_rect = QRect(0, 0, diameter, diameter)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, 1))
        painter.drawEllipse(QPointF(self.rect().center()), diameter / 2, diameter / 2)



class LedContainer(QWidget):
    def __init__(self, task_list):
        super().__init__()
        self.task_list = task_list
        self.layout = QHBoxLayout()

    def create_led_indicators(self):
        self.progress_led_dict = {}

        for task in self.task_list:
            #create an LED indicator for each task in the task list
            led_indicator = LEDIndicator()
            self.progress_led_dict[task] = led_indicator

            led_label = QLabel(task.capitalize())
            led_label.setStyleSheet(label_stylesheet)

            led_item_layout = QHBoxLayout()
            led_item_layout.addWidget(led_indicator)
            led_item_layout.addWidget(led_label)

            self.layout.addLayout(led_item_layout)

        self.layout.addStretch()

        return self.progress_led_dict, self.layout
    
    def change_leds_to_tasks_not_started_color(self):
        #reset all LEDs
        for led_indicator in self.progress_led_dict.values():
            led_indicator.set_not_started_process_color()

    
    def change_led_to_task_not_started_color(self, task):
        #reset a single LED
        if task in self.progress_led_dict:
            self.progress_led_dict[task].set_not_started_process_color()

    def change_led_to_task_is_running_color(self,task):
        if task in self.progress_led_dict:
            self.progress_led_dict[task].set_in_process_color()

    def change_led_to_task_is_finished_color(self,task):
            if task in self.progress_led_dict:
                self.progress_led_dict[task].set_finished_process_color()

