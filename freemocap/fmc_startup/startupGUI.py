import tkinter as tk
from tkinter import Tk, Label, Button, Frame, Listbox, Entry, filedialog
from pathlib import Path

from numpy.lib.npyio import save

class setDataPathGUI:
    def __init__(self, master,session):
        self.master = master
        self.session = session
    
        chooseText = "Please choose the directory your FreeMoCap_data folder is located in"
        chooseLabel = Label(master, text=chooseText)
        chooseLabel.pack(side="top")

        self.currentPath = session.preferences['saved']['path_to_save'] 
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


class DLCConfigPathGUI:
    def __init__(self,master,session,saved_dlc_paths):
        #saved_dlc_paths = ['one','two','three']
        self.master = master
        self.dlc_paths = saved_dlc_paths.copy()
        self.session = session

        introText = "Here are your currently saved DLC config paths"
        introLabel = Label(master, text=introText)
        introLabel.pack(side="top")

        #savedPathText = self.write_to_string(saved_dlc_paths)
        self.savedPathVar = tk.StringVar()
        #savedPathVar.set(savedPathText)
        self.update_dlc_path_label(self.dlc_paths)
        savedPathLabel = Label(master,textvariable=self.savedPathVar)
        savedPathLabel.pack()

        addpath_button = Button(master,text = 'Add a file path',command = self.openFileDialog)
        addpath_button.pack(side='top')

        clearpath_button = Button(master,text = 'Clear file paths',command = self.clearPaths)
        clearpath_button.pack(side='top')

        savepath_button =  Button(master,text = 'Save file paths and Proceed',command = self.savePaths)
        savepath_button.pack(side = 'top')


    def update_dlc_path_label(self,saved_dlc_paths):
        dlc_string_list = '\n'.join(saved_dlc_paths)
        self.savedPathVar.set(dlc_string_list)
        return dlc_string_list

    def openFileDialog(self):
        chosen_path = filedialog.askopenfilename(
        title='Open a file',
        initialdir= Path.cwd(),
        filetypes=[('Yaml','*.yaml')])
        self.dlc_paths.append(chosen_path)
        self.update_dlc_path_label(self.dlc_paths)
        f = 2
    
    def clearPaths(self):
        self.dlc_paths = []
        self.update_dlc_path_label(self.dlc_paths)

    def savePaths(self):
        self.config_paths= self.dlc_paths
        self.master.destroy()


        f = 2   
    



class setBlenderPathGUI:
    def __init__(self, master,session):
        self.master = master
        self.session = session
    
        chooseText = "Choose your Blender executable"
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
        self.currentPath = filedialog.askopenfilename(
        title='Open your Blender executable',
        initialdir= Path.cwd())
        self.currentPathText.set('Current file path: ' + self.currentPath)

    
    def stop(self):
        self.master.destroy()

    
    def proceed(self):
        self.continueToRecording = True
        self.dataPath = self.currentPath
        self.master.destroy()


def RunChooseBlenderPathGUI(session):
    root = tk.Tk()
    chosenBlenderPath = setBlenderPathGUI(root, session)
    root.mainloop()

    return chosenBlenderPath.dataPath




def RunChooseDataPathGUI(session):
    root = tk.Tk()
    chosenDataPath = setDataPathGUI(root, session)
    root.mainloop()

    return Path(chosenDataPath.dataPath)


def RunChooseDLCPathGUI(session,saved_dlc_paths):
    root = tk.Tk()
    chosenDLCPaths = DLCConfigPathGUI(root,session,saved_dlc_paths)
    root.mainloop()

    return chosenDLCPaths.config_paths

    f = 2

  