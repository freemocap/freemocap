from requests import session
import freemocap 
freemocap.RunMe(sessionID='sesh_2022-05-19_17_08_50', stage=3, useBlender=True, annotate)


#####################
### freemocap.RunMe() - Default parameters
#####################

# def RunMe(sessionID=None,
#         stage=1,
#         useOpenPose=False,
#         runOpenPose = True,
#         useMediaPipe=True,
#         runMediaPipe=True,
#         useDLC=False,
#         dlcConfigPath=None,
#         debug=False,
#         setDataPath = False,
#         userDataPath = None,
#         recordVid = True,
#         showAnimation = True,
#         reconstructionConfidenceThreshold = .5,
#         charucoSquareSize = 36,#mm - ~the size of the squares when printed on 8.5x11" paper based on parameters in ReadMe.md
#         calVideoFrameLength = 1,
#         startFrame = 0,
#         useBlender = False,
#         resetBlenderExe = False,
#         get_synced_unix_timestamps = True,
#         good_clean_frame_number = 0,
#         use_saved_calibration = False,
#         bundle_adjust_3d_points=False,
#         place_skeleton_on_origin = False,
#         save_annotated_videos = False,
#         ):