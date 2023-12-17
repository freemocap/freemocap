# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import sys

from PySide6.QtCore import (QDateTime, QDir, QLibraryInfo, QSysInfo, Qt,
                            QTimer, Slot, qVersion)
from PySide6.QtGui import (QCursor, QIcon,
                           QKeySequence, QShortcut, QStandardItem,
                           QStandardItemModel)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox,
                               QCommandLinkButton, QDateTimeEdit, QDial,
                               QDialog, QDialogButtonBox, QFileSystemModel,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListView, QMenu, QPlainTextEdit,
                               QProgressBar, QPushButton, QRadioButton,
                               QScrollBar, QSizePolicy, QSlider, QSpinBox,
                               QStyleFactory, QTableWidget, QTabWidget,
                               QTextBrowser, QTextEdit, QToolBox, QToolButton,
                               QTreeView, QVBoxLayout)

from experimental.batch_process.batch_processing_widget.widgetsgallery.constants import POEM, DIR_OPEN_ICON, \
    COMPUTER_ICON, SYSTEMINFO
from experimental.batch_process.batch_processing_widget.widgetsgallery.helpers import launch_help, launch_module_help, \
    init_widget, style_names, embed_into_hbox_layout, screen_info
from freemocap.gui.qt.widgets.control_panel.process_mocap_data_panel.process_motion_capture_data_panel import \
    ProcessMotionCaptureDataPanel



class WidgetGallery(QDialog):
    """Dialog displaying a gallery of Qt Widgets"""

    def __init__(self):
        super().__init__()

        self.setWindowIcon(QIcon(':/qt-project.org/logos/pysidelogo.png'))
        self._progress_bar = self.create_progress_bar()

        self._style_combobox = QComboBox()
        init_widget(self._style_combobox, "styleComboBox")
        self._style_combobox.addItems(style_names())

        style_label = QLabel("Style:")
        init_widget(style_label, "style_label")
        style_label.setBuddy(self._style_combobox)

        help_label = QLabel("Press F1 over a widget to see Documentation")
        init_widget(help_label, "help_label")


        buttons_groupbox = self.create_buttons_groupbox()
        itemview_tabwidget = self.create_itemview_tabwidget()
        simple_input_widgets_groupbox = self.create_simple_inputwidgets_groupbox()
        # text_toolbox = self.create_text_toolbox()

        self._style_combobox.textActivated.connect(self.change_style)


        help_shortcut = QShortcut(self)
        help_shortcut.setKey(QKeySequence.HelpContents)
        help_shortcut.activated.connect(self.help_on_current_widget)

        top_layout = QHBoxLayout()
        top_layout.addWidget(style_label)
        top_layout.addWidget(self._style_combobox)
        top_layout.addStretch(1)
        top_layout.addWidget(help_label)
        top_layout.addStretch(1)
        # top_layout.addWidget(disable_widgets_checkbox)

        dialog_buttonbox = QDialogButtonBox(QDialogButtonBox.Help
                                            | QDialogButtonBox.Close)
        init_widget(dialog_buttonbox, "dialogButtonBox")
        dialog_buttonbox.helpRequested.connect(launch_module_help)
        dialog_buttonbox.rejected.connect(self.reject)

        main_layout = QGridLayout(self)
        main_layout.addLayout(top_layout, 0, 0, 1, 2)
        # main_layout.addWidget(buttons_groupbox, 1, 0)

        main_layout.addWidget(itemview_tabwidget, 2, 0)
        main_layout.addWidget(simple_input_widgets_groupbox, 2, 1)
        # main_layout.addWidget(text_toolbox, 2, 1)
        main_layout.addWidget(self._progress_bar, 3, 0, 1, 2)
        main_layout.addWidget(dialog_buttonbox, 4, 0, 1, 2)

        qv = qVersion()
        self.setWindowTitle(f"Widget Gallery Qt {qv}")

    def setVisible(self, visible):
        super(WidgetGallery, self).setVisible(visible)
        if visible:
            self.windowHandle().screenChanged.connect(self.update_systeminfo)
            self.update_systeminfo()

    @Slot(str)
    def change_style(self, style_name):
        QApplication.setStyle(QStyleFactory.create(style_name))

    @Slot()
    def advance_progressbar(self):
        cur_val = self._progress_bar.value()
        max_val = self._progress_bar.maximum()
        self._progress_bar.setValue(cur_val + (max_val - cur_val) / 100)

    def create_buttons_groupbox(self):
        result = QGroupBox("Buttons")
        init_widget(result, "buttons_groupbox")

        default_pushbutton = QPushButton("Default Push Button")
        init_widget(default_pushbutton, "default_pushbutton")
        default_pushbutton.setDefault(True)

        toggle_pushbutton = QPushButton("Toggle Push Button")
        init_widget(toggle_pushbutton, "toggle_pushbutton")
        toggle_pushbutton.setCheckable(True)
        toggle_pushbutton.setChecked(True)

        flat_pushbutton = QPushButton("Flat Push Button")
        init_widget(flat_pushbutton, "flat_pushbutton")
        flat_pushbutton.setFlat(True)

        toolbutton = QToolButton()
        init_widget(toolbutton, "toolButton")
        toolbutton.setText("Tool Button")

        menu_toolbutton = QToolButton()
        init_widget(menu_toolbutton, "menuButton")
        menu_toolbutton.setText("Menu Button")
        tool_menu = QMenu(menu_toolbutton)
        menu_toolbutton.setPopupMode(QToolButton.InstantPopup)
        tool_menu.addAction("Option")
        tool_menu.addSeparator()
        action = tool_menu.addAction("Checkable Option")
        action.setCheckable(True)
        menu_toolbutton.setMenu(tool_menu)
        tool_layout = QHBoxLayout()
        tool_layout.addWidget(toolbutton)
        tool_layout.addWidget(menu_toolbutton)

        commandlinkbutton = QCommandLinkButton("Command Link Button")
        init_widget(commandlinkbutton, "commandLinkButton")
        commandlinkbutton.setDescription("Description")

        button_layout = QVBoxLayout()
        button_layout.addWidget(default_pushbutton)
        button_layout.addWidget(toggle_pushbutton)
        button_layout.addWidget(flat_pushbutton)
        button_layout.addLayout(tool_layout)
        button_layout.addWidget(commandlinkbutton)
        button_layout.addStretch(1)

        radiobutton_1 = QRadioButton("Radio button 1")
        init_widget(radiobutton_1, "radioButton1")
        radiobutton_2 = QRadioButton("Radio button 2")
        init_widget(radiobutton_2, "radioButton2")
        radiobutton_3 = QRadioButton("Radio button 3")
        init_widget(radiobutton_3, "radioButton3")
        radiobutton_1.setChecked(True)

        checkbox = QCheckBox("Tri-state check box")
        init_widget(checkbox, "checkBox")
        checkbox.setTristate(True)
        checkbox.setCheckState(Qt.PartiallyChecked)

        checkable_layout = QVBoxLayout()
        checkable_layout.addWidget(radiobutton_1)
        checkable_layout.addWidget(radiobutton_2)
        checkable_layout.addWidget(radiobutton_3)
        checkable_layout.addWidget(checkbox)
        checkable_layout.addStretch(1)

        main_layout = QHBoxLayout(result)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(checkable_layout)
        main_layout.addStretch()
        return result

    def create_text_toolbox(self):
        result = QToolBox()
        init_widget(result, "toolBox")

        # Create centered/italic HTML rich text
        rich_text = "<html><head/><body><i>"
        for line in POEM.split('\n'):
            rich_text += f"<center>{line}</center>"
        rich_text += "</i></body></html>"

        text_edit = QTextEdit(rich_text)
        init_widget(text_edit, "textEdit")
        plain_textedit = QPlainTextEdit(POEM)
        init_widget(plain_textedit, "plainTextEdit")

        self._systeminfo_textbrowser = QTextBrowser()
        init_widget(self._systeminfo_textbrowser, "systemInfoTextBrowser")

        result.addItem(embed_into_hbox_layout(text_edit), "Text Edit")
        result.addItem(embed_into_hbox_layout(plain_textedit),
                       "Plain Text Edit")
        result.addItem(embed_into_hbox_layout(self._systeminfo_textbrowser),
                       "Text Browser")
        return result

    def create_itemview_tabwidget(self):
        result = QTabWidget()
        init_widget(result, "bottomLeftTabWidget")
        result.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)

        tree_view = QTreeView()
        init_widget(tree_view, "treeView")
        filesystem_model = QFileSystemModel(tree_view)
        filesystem_model.setRootPath(QDir.rootPath())
        tree_view.setModel(filesystem_model)

        table_widget = QTableWidget()
        init_widget(table_widget, "tableWidget")
        table_widget.setRowCount(10)
        table_widget.setColumnCount(10)

        list_model = QStandardItemModel(0, 1, result)

        list_model.appendRow(QStandardItem(QIcon(DIR_OPEN_ICON), "Directory"))
        list_model.appendRow(QStandardItem(QIcon(COMPUTER_ICON), "Computer"))

        list_view = QListView()
        init_widget(list_view, "listView")
        list_view.setModel(list_model)

        icon_mode_listview = QListView()
        init_widget(icon_mode_listview, "iconModeListView")

        icon_mode_listview.setViewMode(QListView.IconMode)
        icon_mode_listview.setModel(list_model)

        result.addTab(embed_into_hbox_layout(tree_view), "Tree View")
        result.addTab(embed_into_hbox_layout(table_widget), "Table")
        result.addTab(embed_into_hbox_layout(list_view), "List")
        result.addTab(embed_into_hbox_layout(icon_mode_listview),
                      "Icon Mode List")
        return result

    def create_simple_inputwidgets_groupbox(self):
        result = QGroupBox("Simple Input Widgets")
        init_widget(result, "bottomRightGroupBox")
        result.setCheckable(True)
        result.setChecked(True)

        lineedit = QLineEdit("s3cRe7")
        init_widget(lineedit, "lineEdit")
        lineedit.setClearButtonEnabled(True)
        lineedit.setEchoMode(QLineEdit.Password)

        spin_box = QSpinBox()
        init_widget(spin_box, "spinBox")
        spin_box.setValue(50)

        date_timeedit = QDateTimeEdit()
        init_widget(date_timeedit, "dateTimeEdit")
        date_timeedit.setDateTime(QDateTime.currentDateTime())

        slider = QSlider()
        init_widget(slider, "slider")
        slider.setOrientation(Qt.Horizontal)
        slider.setValue(40)

        scrollbar = QScrollBar()
        init_widget(scrollbar, "scrollBar")
        scrollbar.setOrientation(Qt.Horizontal)
        scrollbar.setValue(60)

        dial = QDial()
        init_widget(dial, "dial")
        dial.setValue(30)
        dial.setNotchesVisible(True)

        layout = QGridLayout(result)
        layout.addWidget(lineedit, 0, 0, 1, 2)
        layout.addWidget(spin_box, 1, 0, 1, 2)
        layout.addWidget(date_timeedit, 2, 0, 1, 2)
        layout.addWidget(slider, 3, 0)
        layout.addWidget(scrollbar, 4, 0)
        layout.addWidget(dial, 3, 1, 2, 1)
        layout.setRowStretch(5, 1)
        return result

    def create_progress_bar(self):
        result = QProgressBar()
        init_widget(result, "progressBar")
        result.setRange(0, 10000)
        result.setValue(0)

        timer = QTimer(self)
        timer.timeout.connect(self.advance_progressbar)
        timer.start(1000)
        return result

    @Slot()
    def update_systeminfo(self):
        """Display system information"""
        system_info = SYSTEMINFO.format(sys.version,
                                        QLibraryInfo.build(),
                                        QSysInfo.prettyProductName(),
                                        screen_info(self))
        # self._systeminfo_textbrowser.setHtml(system_info)

    @Slot()
    def help_on_current_widget(self):
        """Display help on widget under mouse"""
        w = QApplication.widgetAt(QCursor.pos(self.screen()))
        while w:  # Skip over internal widgets
            name = w.objectName()
            if name and not name.startswith("qt_"):
                launch_help(w)
                break
            w = w.parentWidget()
