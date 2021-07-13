import tkinter as tk
from tkinter import Tk, Label, Button, Frame, Listbox, Entry, filedialog
from pathlib import Path

class setDataPathGUI:
    def __init__(self, master,session):
        self.master = master
        self.session = session
    
        chooseText = "Choose the directory where your data folder is located"
        chooseLabel = Label(master, text=chooseText)
        chooseLabel.pack(side="top")

        self.currentPath = Path.cwd()
        text = 'Current file path: ' + str(self.currentPath)
        self.currentPathText = tk.StringVar()
        self.currentPathText.set(text)
        currentPathLabel = Label(master,textvariable = self.currentPathText)
        currentPathLabel.pack()

        changepath_button = Button(master,text = 'Change Folder Path',command = self.openFileDialog)
        changepath_button.pack(side = 'left')

        proceed_button = Button(text="Proceed", command=self.proceed)
        stop_button = Button(text="Quit", command=self.stop)
        proceed_button.pack()
        stop_button.pack()



    def openFileDialog(self):
        self.currentPath = filedialog.askdirectory(
        title='Open a file',
        initialdir= Path.cwd())
        self.currentPathText.set('Current file path: ' + self.currentPath)

    
    def stop(self):
        self.master.destroy()

    
    def proceed(self):
        self.continueToRecording = True
        self.dataPath = self.currentPath
        self.master.destroy()


def RunChooseDataPathGUI(session):
    root = tk.Tk()
    chosenDataPath = setDataPathGUI(root, session)
    root.mainloop()

    return chosenDataPath.dataPath