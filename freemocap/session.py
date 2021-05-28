class Session: #session like "recording session"
    def __init__(self, useOpenPose, useDLC):
        self.sessionID = '' #The sessionID tag will be used to generate files names and whatnot
        self.sessionPath = '' #The folder where the to-be-processed videos live (in a folder called "synced Vids")
        self.numCams = ''#The number of cameras used in this recording session
        self.openPoseDataPath   = ''#Where the open pose data lives
        self.dlcDataPath    = ''#Where the DLC data lives
        self.useOpenPose = useOpenPose
        self.useDLC = useDLC
        self.openPoseExePath = r'C:\openpose'

        self.cam_inputs = None
        self.parameterDictionary = None
        self.rotationInputs = None
        
    