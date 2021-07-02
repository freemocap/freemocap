from pathlib import Path
from ruamel.yaml import YAML

from freemocap import recordingconfig

class Session: #self like "recording self"
    def __init__(self):
        
        self.numCams = None
        self.numFrames = None
        self.numTrackedPoints = None 

        self.basePath = Path.cwd()
        
        self.sessionID = '' #The sessionID tag will be used to generate files names and whatnot
        self.sessionPath = '' #The folder where the to-be-processed videos live (in a folder called "synced Vids")
        #self.numCams = ''#The number of cameras used in this recording self
        self.openPoseDataPath   = ''#Where the open pose data lives
        self.dlcDataPath    = ''#Where the DLC data lives
        self.openPoseExePath = r'C:\openpose'

        self.cam_inputs = None
        self.parameterDictionary = None
        self.rotationInputs = None

        self.cgroup = None

        self.mean_charuco_fr_mar_dim = None
        self.skel_fr_mar_dim = None

        self.mediaPipe_imgPathList = None
        self.openPose_imgPathList = None

    def start_session(self,paramDict,rotDict):
        #start a session, create all the file paths necessary, and create a session dictionary to save settings
        recordPath = self.basePath/'Data'
        recordPath.mkdir(exist_ok= True)

        self.sessionPath = recordPath/self.sessionID
        self.sessionPath.mkdir(exist_ok=True)

        #create all the session filepaths and settings - create and load them into a dictionary
        self.pathList = self.create_session_paths()
        self.session_settings = self.create_session_dictionary()
        self.create_session_txt(paramDict,rotDict)

        self.save_session()



    def create_session_paths(self):
        #creates Path objects to each folder created in a recording self and adds them all to the pathList variable
        #folders for these paths are created at the start of each stage where they are needed 

        pathList = []

        self.rawVidPath = self.sessionPath/'RawVideos'
        pathList.append(self.rawVidPath)

        self.syncedVidPath = self.sessionPath/'SyncedVideos'
        pathList.append(self.syncedVidPath)

        self.calVidPath = self.sessionPath/'CalVideos'
        pathList.append(self.calVidPath)

        self.dataArrayPath = self.sessionPath/'DataArrays'
        pathList.append(self.dataArrayPath)

        self.dlcDataPath = self.sessionPath/'DLCData'
        pathList.append(self.dlcDataPath)

        self.openPoseDataPath = self.sessionPath/'OpenPoseData'
        pathList.append(self.openPoseDataPath)

        self.mediaPipeDataPath = self.sessionPath/'MediaPipeData'
        pathList.append(self.mediaPipeDataPath)

        self.imOutPath = self.sessionPath/'imOut'
        pathList.append(self.imOutPath)
        
        return pathList

    def create_session_dictionary(self):
        #creates a dictionary of settings that should be saved into a YAML throughout each self

        recording_parameters = {'numCams': self.numCams, 'numFrames': self.numFrames, 'numTrackedPoints': self.numTrackedPoints}

        #create a dictionary with the folder names (taken from the recordingconfig.py file) and the folder paths from pathList
        #NOTE AC- 6/30/21 - as of right now, the order of folder names in the recordingconfig.folder_setup list needs to match the 
        #                the order of folder paths in the pathList
        session_paths = {}

        for foldername, folderpath in zip(recordingconfig.folder_setup,self.pathList):
            session_paths[foldername] = folderpath

        session_settings_dictionary = {'recording_parameters':recording_parameters, 'session_paths':session_paths}
        
        return session_settings_dictionary


    def create_session_txt(self,paramDict,rotDict):
    #create a text file listing recording parameters
        parameter_text = self.sessionPath/'sessionSettings.txt' 
        text = open(parameter_text, 'w')
        text.write("Session ID = %s\n" %(self.sessionID))
        text.write("%s = %s\n" %("Parameters", paramDict))
        text.write("%s = %s\n" %("Rotations", rotDict))
        text.close()

    def save_session(self):
        #save the self settings you want to keep from self to self into a yaml
        #because some items are not yaml-able, a copy of the sessionDictionary is made and adjusted to be fully yaml-able
            #Adjustments Made:
                #pathLib objects are all converted to strings
        session_dictionary_to_save = self.session_settings

        for key,value in session_dictionary_to_save['session_paths'].items():
            session_dictionary_to_save['session_paths'][key] = str(value)

        self.session_yaml_path = self.sessionPath/'{}_config.yaml'.format(self.sessionID)
        
        session_yaml = YAML()
        

        with open(self.session_yaml_path,'w') as outfile:
            session_yaml.dump(session_dictionary_to_save,outfile)

   
    def initialize(self,stage):
        #load all session settings back into the session class for this run-through of the code
        
        recordPath = self.basePath/'Data' #create a Data folder in the filepath if none exists yet
        recordPath.mkdir(exist_ok= True)

        self.sessionPath = recordPath/self.sessionID
        self.sessionPath.mkdir(exist_ok=True)

        self.session_yaml_path = self.sessionPath/'{}_config.yaml'.format(self.sessionID)

        if stage == 3:
            #this is for the case of GoPro recordings/external recordings - if no config file exists, create one
            if self.session_yaml_path.is_file():
                self.session_settings = self.load_session()
            else: 
                self.start_session({},{})
        else:
            self.session_settings = self.load_session()
        


   
    def load_session(self):

        #session_yaml_path = self.sessionPath/'{}_config.yaml'.format(self.sessionID)
        session_yaml = YAML(typ='safe', pure=True)

        with open(self.session_yaml_path,'r') as fp:
            session_dictionary_to_load = session_yaml.load(fp)

        session_settings_dictionary = session_dictionary_to_load #create a copy of the loaded dictionary

        for key,value in session_settings_dictionary['session_paths'].items():
            session_settings_dictionary['session_paths'][key] = Path(value)

        self.load_session_paths(session_settings_dictionary)
        self.numCams = session_settings_dictionary['recording_parameters']['numCams']
        self.numFrames = session_settings_dictionary['recording_parameters']['numFrames']
        self.numTrackedPoints = session_settings_dictionary['recording_parameters']['numTrackedPoints']

        return session_settings_dictionary
        f = 2
    
    def load_session_paths(self, session_settings_dict):

        session_paths = session_settings_dict['session_paths']

        self.rawVidPath = session_paths['RawVideos']
        self.syncedVidPath = session_paths['SyncedVideos']
        self.calVidPath = session_paths['CalVideos']
        self.mediaPipeDataPath = session_paths['MediaPipeData']
        self.openPoseDataPath = session_paths['OpenPoseData']
        self.dlcDataPath = session_paths['DLCData']
        self.imOutPath = session_paths['imOut']
        self.dataArrayPath = session_paths['DataArrays']

        

        f = 2

    
        


        

        
            

    


  


