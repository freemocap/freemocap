import sys
import time
# Import QApplication and the required widgets from PyQt5.QtWidgets


from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QLabel
from test_iPython_gui import IPythonConsoleWidget

from PyQt5.QtGui import QPixmap

import freemocap as fmc

sessionParam_dict = {
                    "useOpenPose": False, 
}

def import_fmc():
    
    import_text = 'import freemocap as fmc'
    print('sending command:' + import_text)

    iPyWidget.print_text(import_text)
    iPyWidget.execute_command(import_text)
    
def set_useOpenPose(useOpenPose_button):

    if useOpenPose_button.isChecked():
        sessionParam_dict['useOpenPose'] = True
        runMeButton.setText('fmc.RunMe(useOpenPose=True)')
    else:
        sessionParam_dict['useOpenPose'] = False
        runMeButton.setText('fmc.RunMe()')


def run_fmc():
    useOpenPoseBool = sessionParam_dict['useOpenPose']
    fmc.RunMe(useOpenPose=useOpenPoseBool)
    
    # fmc_runme_text = 'fmc.RunMe()'
    # print('sending command:' + fmc_runme_text)
    
    # iPyWidget.print_text(fmc_runme_text)    
    # iPyWidget.execute_command(fmc_runme_text)
    
app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle('PyQT Test')

main_layout = QHBoxLayout() #This is the whole GUI window

# logo_label = QLabel()
# logo_pixmap = QPixmap('freemocap-logo--blackOutline_squareTransCanvas-01.png')
# logo_label.setPixmap(logo_pixmap)
# logo_label.setScaledContents(True)
# main_layout.addWidget(logo_label)


#Make a vertical box of check boxes
button_layout = QVBoxLayout()

useOpenPose_button = QCheckBox('useOpenPose')
useOpenPose_button.stateChanged.connect(set_useOpenPose)
button_layout.addWidget(QCheckBox('useOpenPose'))
# button_layout.addWidget(QCheckBox('useDLC'))
# button_layout.addWidget(QCheckBox('useMediaPipe'))

# importFMC_button = QPushButton('import freemocap as fmc')
# importFMC_button.clicked.connect(import_fmc)
# button_layout.addWidget(importFMC_button)


runMeButton = QPushButton('fmc.RunMe()')
runMeButton.clicked.connect(run_fmc)
button_layout.addWidget(runMeButton)

main_layout.addLayout(button_layout)


#Add the IpYthon console widget
iPyWidget = IPythonConsoleWidget()
main_layout.addWidget(iPyWidget)
iPyWidget.print_text('import freemocap as fmc')

window.setLayout(main_layout)

window.show()
sys.exit(app.exec_())