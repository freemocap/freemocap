# -*- coding: utf-8 -*-
"""
Created on Thu Mar 11 11:54:12 2021

@author: Rontc
"""

from pathlib import Path


dataFolder = 'FreeMocap_Data'


folder_setup = ['RawVideos','SyncedVideos','CalVideos','DataArrays','DLCData','OpenPoseData','MediaPipeData','imOut']

default_parameters = {'path_to_save': str(Path.home()),'dlc_config_paths':[], 'rotations':{},'parameters':{'exposure':-5,'resWidth':640,'resHeight':480,'framerate':25,'codec':'DIVX'}, 'blenderEXEpath':None}
saved_parameters = default_parameters
parameters_for_yaml = {'default':default_parameters,'saved':saved_parameters}




# def createSession(session,filepath, existing_data = False):
#     #create file paths for the session, raw and synced videos
    
#     pathList = []
   
#     recordPath = filepath/'Data'
#     recordPath.mkdir(exist_ok= True)
    
#     session.sessionPath = recordPath/session.sessionID
#     #if existing_data:
#         #session.sessionPath.mkdir(exist_ok = True)
#     #else:
#     session.sessionPath.mkdir(exist_ok= True)
#     pathList.append(session.sessionPath)
    
#     session.rawVidPath = session.sessionPath/'RawVideos'
#     session.rawVidPath.mkdir(exist_ok = True)
#     pathList.append(session.rawVidPath)

#     session.syncedVidPath = session.sessionPath/'SyncedVideos'   
#     session.syncedVidPath.mkdir(exist_ok = True)
#     pathList.append(session.syncedVidPath)

#     session.calVidPath = session.sessionPath/'CalVideos'
#     session.calVidPath.mkdir(exist_ok = True)
#     pathList.append(session.calVidPath)

#     session.openPoseDataPath = session.sessionPath/'OpenPoseData'
#     session.openPoseDataPath.mkdir(exist_ok = True)
#     pathList.append(session.openPoseDataPath)

#     session.mediaPipeDataPath = session.sessionPath/'MediaPipeData'
#     session.mediaPipeDataPath.mkdir(exist_ok = True)
#     pathList.append(session.mediaPipeDataPath)
    
#     session.dlcDataPath  =  session.sessionPath / 'DLCdata'
#     session.dlcDataPath.mkdir(exist_ok = True, parents = True)
#     pathList.append(session.dlcDataPath)
    
#     session.imOutPath = session.sessionPath / 'imOut'
#     session.imOutPath.mkdir(exist_ok=True)
#     pathList.append(session.imOutPath)

#     session.dataArrayPath = session.sessionPath/'Data Arrays'
#     session.dataArrayPath.mkdir(exist_ok=True)
#     pathList.append(session.dataArrayPath)
    
#     #create a list of paths that is passed to the recording script
#     #pathList = [session.sessionPath,session.rawVidPath,session.syncedVidPath,session.openPoseDataPath,session.dlcDataPath,session.imOutPath, session.dataArrayPath]
   
    
#     config_settings,config_yaml = create_config_yaml()
#     session.config_settings = config_settings

#     yaml_name = session.sessionPath/'{}_config.yaml'.format(session.sessionID)
#     session.yamlPath = yaml_name
#    # print(yaml_name)
#     write_config_yaml(session,config_settings,config_yaml,pathList,yaml_name)
    
#     return yaml_name

# def createSessionTxt(session,paramDict,rotDict):
#     #create a text file listing recording parameters
#     parameter_text = session.sessionPath/'sessionSettings.txt' 
#     text = open(parameter_text, 'w')
#     text.write("Session ID = %s\n" %(session.sessionID))
#     text.write("%s = %s\n" %("Parameters", paramDict))
#     text.write("%s = %s\n" %("Rotations", rotDict))
#     text.close()
    
    
    

# def create_config_yaml():

# def create_config_yaml():

#     yaml_str = """\
#     # Camera Inputs
#     CamInputs:
#         RotationInputs:
#         ParameterDict:

#     # Paths
#     Paths:
#         sessionPath: 
#         rawVidPath:
#         syncedVidPath:
#         calVidPath:
#         openPoseDataPath:
#         mediaPipeDataPath:
#         dlcDataPath:
#         imOutPath:
#         dataArrayPath:
#         \n
#         """
#     config_yaml = YAML()
#     config_settings = config_yaml.load(yaml_str)

#     return config_settings,config_yaml

# def write_config_yaml(session, config_settings, config_yaml, pathList, yaml_name):

# def write_config_yaml(session,config_settings,config_yaml,pathList,yaml_name):
    
#     for count,key in enumerate(config_settings['Paths'].keys()):
#         config_settings['Paths'][key] = str(pathList[count])
    
#     config_settings['CamInputs']['RotationInputs'] = session.rotationInputs
#     config_settings['CamInputs']['ParameterDict'] = session.parameterDictionary
    

#     #yamlPath = sessionPath/'config_yaml'
#     #print(config_settings,yaml_name)
#     with open(yaml_name, 'w') as outfile:
#         config_yaml.dump(config_settings, outfile)


# def load_config_yaml(yaml_path):
#     config_yaml = YAML()
#     with open(yaml_path,'r') as fp:
#         config_settings = config_yaml.load(fp)
#     return config_settings

# def load_session_paths(session,config_settings):
#     configPaths = config_settings['Paths']
#     session.rawVidPath = Path(configPaths['rawVidPath'])
#     session.syncedVidPath = Path(configPaths['syncedVidPath'])
#     session.calVidPath = Path(configPaths['calVidPath'])
#     session.mediaPipeDataPath = Path(configPaths['mediaPipeDataPath'])
#     session.openPoseDataPath = Path(configPaths['openPoseDataPath'])
#     session.dlcDataPath = Path(configPaths['dlcDataPath'])
#     session.imOutPath = Path(configPaths['imOutPath'])
#     session.dataArrayPath = Path(configPaths['dataArrayPath'])
