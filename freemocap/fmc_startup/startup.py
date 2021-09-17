from pathlib import Path

from ruamel.yaml import YAML

from freemocap import recordingconfig
from freemocap.fmc_startup import startupGUI

def get_user_preferences(session,stage):
    """
    load user preferences if they exist, create a new preferences yaml if they don't
    """
    here = Path(__file__).parent
    preferences_path = here/'user_preferences.yaml' 
    preferences_yaml = YAML()

    #check for a user preferences yaml, if it doesn't exist, build one using the default parameters in recordingconfig.py   
    if preferences_path.exists():
        preferences = preferences_yaml.load(preferences_path)
    else:
        preferences = recordingconfig.parameters_for_yaml
        preferences_yaml.dump(preferences, preferences_path)
    
    session.preferences = preferences
    session.preferences_path = preferences_path
        
def get_dlc_paths(session):
        try:
            saved_dlc_paths = session.preferences['saved']['dlc_config_paths']
        except: 
            saved_dlc_paths = session.preferences['default']['dlc_config_paths']

        dlc_config_paths = startupGUI.RunChooseDLCPathGUI(session,saved_dlc_paths)
        
        session.preferences['saved']['dlc_config_paths'] = dlc_config_paths
        session.save_user_preferences(session.preferences)
        return dlc_config_paths

def get_data_folder_path(session):
        #if we are rerunning a session folder
        # 1) Check if we're using the last saved dataFolderPath, or if the user wants to choose a different one
        #   a. if the user wants to choose one, bring up a GUI to let them decide
        #   b. if we're using the last known path - parse the user preferences yaml (and check if that yaml exists)
        # 2) Check that the data folder exists
        # 3) If no sessionID was user-input, search the chosen directory for the last session created
        if session.setDataPath == True:
            session.basePath = startupGUI.RunChooseDataPathGUI(session)
            session.basePath = Path(session.basePath)
            #sesh.dataFolderPath = Path(basePath)/sesh.dataFolderName

        elif session.userDataPath is not None:
            session.basePath = session.userDataPath
        
        else:
            try:
                current_path_to_data = session.preferences['saved']['path_to_save']
                session.basePath = current_path_to_data
            except KeyError:
                print('Saved Data path not found, please choose a new one')
                session.basePath = startupGUI.RunChooseDataPathGUI(session)
                session.preferences['saved']['path_to_save'] = str(session.basePath)
                session.save_user_preferences(session.preferences)


        dataFolder = Path(session.basePath)/session.dataFolderName
        session.dataFolderPath = dataFolder
        
        if not dataFolder.exists():
            raise FileNotFoundError('No data folder located at: ' + str(dataFolder))


