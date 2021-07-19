
"""
============
██████  ██       █████  ██    ██     ███████ ██   ██ ███████ ██      ███████ ████████  ██████  ███    ██      █████  ███    ██ ██ ███    ███  █████  ████████ ██  ██████  ███    ██ 
██   ██ ██      ██   ██  ██  ██      ██      ██  ██  ██      ██      ██         ██    ██    ██ ████   ██     ██   ██ ████   ██ ██ ████  ████ ██   ██    ██    ██ ██    ██ ████   ██ 
██████  ██      ███████   ████       ███████ █████   █████   ██      █████      ██    ██    ██ ██ ██  ██     ███████ ██ ██  ██ ██ ██ ████ ██ ███████    ██    ██ ██    ██ ██ ██  ██ 
██      ██      ██   ██    ██             ██ ██  ██  ██      ██      ██         ██    ██    ██ ██  ██ ██     ██   ██ ██  ██ ██ ██ ██  ██  ██ ██   ██    ██    ██ ██    ██ ██  ██ ██ 
██      ███████ ██   ██    ██        ███████ ██   ██ ███████ ███████ ███████    ██     ██████  ██   ████     ██   ██ ██   ████ ██ ██      ██ ██   ██    ██    ██  ██████  ██   ████                                                                                                                                                                                                                                                                                                                                                                         
============
Font - ANSI Regular - https://patorjk.com/software/taag/#p=display&f=ANSI%20Regular&t=Play%20Skeleton%20Animation
============
Originally based on tutorial from  - https://matplotlib.org/2.1.2/gallery/animation/simple_3danim.html

Create a matplotlib animation from a FreeMoCap recording session.
"""


################################################################################################################
################################################################################################################
###
### ██ ███    ███ ██████   ██████  ██████  ████████ 
### ██ ████  ████ ██   ██ ██    ██ ██   ██    ██    
### ██ ██ ████ ██ ██████  ██    ██ ██████     ██    
### ██ ██  ██  ██ ██      ██    ██ ██   ██    ██    
### ██ ██      ██ ██       ██████  ██   ██    ██    
###
################################################################################################################
################################################################################################################                                                        
                                                        

import numpy as np

import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as p3
import matplotlib.animation as animation
from matplotlib.widgets import Slider
import cv2 

import copy
from pathlib import Path

#RICH CONSOLE STUFF
from rich import pretty
pretty.install() #makes all print statement output pretty
from rich import inspect
from rich.console import Console
console = Console()  
from rich.traceback import install as rich_traceback_install
from rich.markdown import Markdown

#colors from Taylor Davis branding - 
humon_dark = np.array([37, 67, 66])/255
humon_green = np.array([53, 93, 95])/255
humon_blue = np.array([164, 211, 217])/255
humon_red = np.array([217, 81, 87])/255


def PlaySkeletonAnimation(
    session=None,
    vidType=1,
    startFrame=0,
    azimuth=-90,
    elevation=-71,
    numCams=4,
    useCams = None,
    useOpenPose=True,
    useMediaPipe=False,
    useDLC=False,
    recordVid = True
    ):
###  
###
###      ██    ██ ██████  ██████   █████  ████████ ███████         ███████ ██  ██████  ██    ██ ██████  ███████ 
###      ██    ██ ██   ██ ██   ██ ██   ██    ██    ██              ██      ██ ██       ██    ██ ██   ██ ██      
###      ██    ██ ██████  ██   ██ ███████    ██    █████           █████   ██ ██   ███ ██    ██ ██████  █████   
###      ██    ██ ██      ██   ██ ██   ██    ██    ██              ██      ██ ██    ██ ██    ██ ██   ██ ██      
###       ██████  ██      ██████  ██   ██    ██    ███████         ██      ██  ██████   ██████  ██   ██ ███████ 
###                                                                                                               
    def update_figure(frameNum):
        """ 
        Called by matplotlib animator for each frame.
        """
        
        skel_dottos = matplotlib_artist_objs['skel_dottos'] 
        skel_trajectories = figure_data['skel_trajectories|mar|fr_dim']

        if useDLC:
            dlc_dottos = matplotlib_artist_objs['dlc_dottos'] 
            dlc_trajectories = figure_data['dlc_trajectories|mar|fr_dim']

        #function to update the lines for each body segment
        def update_skel_segments(key):       
            """ 
            updates the Artist of each body segment with the current frame data.
            """       
            dict_of_segments_idxs = dict_of_openPoseSegmentIdx_dicts[key]
            dict_of_artists = matplotlib_artist_objs[key] 

            for thisItem in dict_of_segments_idxs.items():
                segName = thisItem[0]
                segArtist = dict_of_artists[segName]
                segArtist.set_data((skel_fr_mar_dim[frameNum-1, dict_of_segments_idxs[segName], 0], skel_fr_mar_dim[frameNum-1, dict_of_segments_idxs[segName], 1]))
                segArtist.set_3d_properties(skel_fr_mar_dim[frameNum-1, dict_of_segments_idxs[segName], 2])                
            
        update_skel_segments('body')
        update_skel_segments('rHand')
        update_skel_segments('lHand')
        update_skel_segments('face')

        #Plots the dots!
        #openpose data
        marNum = -1
        for thisSkelDotto, thisTraj in zip(skel_dottos,skel_trajectories):
            marNum+=1
            # NOTE: there is no .set_data() for 3 dim data...
            thisSkelDotto.set_data(thisTraj[ frameNum-1, 0:2])
            thisSkelDotto.set_3d_properties(thisTraj[ frameNum-1, 2])

        #dlc data
        marNum = -1
        for thisDotto, thisTraj in zip(dlc_dottos,dlc_trajectories):
            marNum+=1
            # NOTE: there is no .set_data() for 3 dim data...
            thisDotto.set_data(thisTraj[ frameNum-1, 0:2])
            thisDotto.set_3d_properties(thisTraj[ frameNum-1, 2])
        
        vidNum = -1
        for thisVidArtist, thisVidDLCArtist, thisVidOpenPoseArtist in zip(vidAristList, vidDLCArtistList, vidOpenPoseArtistList):
            vidNum +=1
            success, image = vidCapObjList[vidNum].read()
            if success:
                thisVidArtist.set_array(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                vidCapObjList[vidNum].set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, image = vidCapObjList[vidNum].read()

            thisVidDLCArtist[0].set_data(  dlcData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum+1,:,0], 
                                    dlcData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum+1,:,1],)

            thisVidOpenPoseArtist[0].set_data(  openPoseData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum,:,0], 
                                    openPoseData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum,:,1],)

        fig.suptitle("SessionID: {}, Frame: {} of {}".format(session.sessionID, frameNum, numFrames))
        # animSlider.set_val(val=frameNum)

####  
####   ██████ ██████  ███████  █████  ████████ ███████     ███████ ██  ██████  ██    ██ ██████  ███████ 
####  ██      ██   ██ ██      ██   ██    ██    ██          ██      ██ ██       ██    ██ ██   ██ ██      
####  ██      ██████  █████   ███████    ██    █████       █████   ██ ██   ███ ██    ██ ██████  █████   
####  ██      ██   ██ ██      ██   ██    ██    ██          ██      ██ ██    ██ ██    ██ ██   ██ ██      
####   ██████ ██   ██ ███████ ██   ██    ██    ███████     ██      ██  ██████   ██████  ██   ██ ███████ 
####                                                                                                    
    

    fig = plt.figure(dpi=150)
    plt.ion()


###  
###   ██████ ██████  ███████  █████  ████████ ███████     ██████        ██████       █████  ██   ██ ██ ███████ 
###  ██      ██   ██ ██      ██   ██    ██    ██               ██       ██   ██     ██   ██  ██ ██  ██ ██      
###  ██      ██████  █████   ███████    ██    █████        █████  █████ ██   ██     ███████   ███   ██ ███████ 
###  ██      ██   ██ ██      ██   ██    ██    ██               ██       ██   ██     ██   ██  ██ ██  ██      ██ 
###   ██████ ██   ██ ███████ ██   ██    ██    ███████     ██████        ██████      ██   ██ ██   ██ ██ ███████ 
###                                                                                                            
###                                                                                                                                                                              

    # ax3d = p3.Axes3D(fig)
    ax3d = fig.add_subplot(projection='3d')
    ax3d.set_position([-.13, .2, .8, .8]) # [left, bottom, width, height])
    ax3d.set_xticklabels([])
    ax3d.set_yticklabels([])
    ax3d.set_zticklabels([])
    ax3d.set_xlabel('X')
    ax3d.set_ylabel('Y')
    ax3d.set_zlabel('Z')
    
    ax3d.tick_params(length=0) # WHY DOESNT THIS WORK? I HATE THOSE TICK MARKS >:(

    try:
        skel_fr_mar_dim = np.load(session.dataArrayPath / 'openPoseSkel_3d.npy')
        openPoseData_nCams_nFrames_nImgPts_XYC = np.load(session.dataArrayPath / 'openPoseData_2d.npy')
    except:
        console.warn('No openPose data found.  This iteration requires OpenPose data')

    figure_data = dict()

    skel_trajectories = [skel_fr_mar_dim[:,markerNum,:] for markerNum in range(skel_fr_mar_dim.shape[1])]
    figure_data['skel_trajectories|mar|fr_dim'] = skel_trajectories
    figure_data['skel_fr_mar_dim'] = skel_fr_mar_dim
    dict_of_openPoseSegmentIdx_dicts, dict_of_skel_lineColor = formatOpenPoseStickIndices() #these will help us draw body and hands stick figures

    if useDLC:
        dlc_fr_mar_dim = np.load(session.dataArrayPath / "deepLabCut_3d.npy")
        dlcData_nCams_nFrames_nImgPts_XYC = np.load(session.dataArrayPath / "deepLabCutData_2d.npy")

        ballTrailLen = 4
    
    dlc_trajectories = [dlc_fr_mar_dim[:,markerNum,:] for markerNum in range(dlc_fr_mar_dim.shape[1])]    
    figure_data['dlc_trajectories|mar|fr_dim'] = dlc_trajectories
    figure_data['dlc_fr_mar_dim'] = dlc_fr_mar_dim

    
    
    
    def build_segment_artist_dict(data_fr_mar_dim, dict_of_list_of_segment_idxs, segColor = 'k', lineWidth = 1, lineStyle = '-'):       
        """ 
        Builds a dictionary of line artists for each body segment.
        """       
        segNames = list(dict_of_list_of_segment_idxs)

        dict_of_artist_objects = dict()
        for segNum, segName in enumerate(segNames):

            #determine color of segment, based on class of 'segColor' input
            if isinstance(segColor, str):
                thisRGBA = segColor
            elif isinstance(segColor, np.ndarray):
                thisRGBA = segColor
            elif isinstance(segColor, dict):
                thisRGBA = segColor[segName]
            elif isinstance(segColor, list):
                try:
                    thisRGBA = segColor[segNum]
                except:
                    print('Not enough colors provided, using Black instead')
                    thisRGBA = 'k'
            else:
                thisRGBA = 'k'


            dict_of_artist_objects[segName]  = ax3d.plot(
                                                    data_fr_mar_dim[0,dict_of_list_of_segment_idxs[segName],0], 
                                                    data_fr_mar_dim[0,dict_of_list_of_segment_idxs[segName],1], 
                                                    data_fr_mar_dim[0,dict_of_list_of_segment_idxs[segName],2],
                                                    linestyle=lineStyle,
                                                    linewidth=lineWidth,
                                                    color = thisRGBA,
                                                    )[0]
        return dict_of_artist_objects

    

    matplotlib_artist_objs = dict()
    matplotlib_artist_objs['body'] = build_segment_artist_dict(skel_fr_mar_dim, dict_of_openPoseSegmentIdx_dicts['body'], segColor = dict_of_skel_lineColor)
    matplotlib_artist_objs['rHand'] = build_segment_artist_dict(skel_fr_mar_dim, dict_of_openPoseSegmentIdx_dicts['rHand'], segColor=np.append(humon_red, 1), lineWidth=1)
    matplotlib_artist_objs['lHand'] = build_segment_artist_dict(skel_fr_mar_dim, dict_of_openPoseSegmentIdx_dicts['lHand'], segColor=np.append(humon_blue, 1), lineWidth=1)
    matplotlib_artist_objs['face'] = build_segment_artist_dict(skel_fr_mar_dim, dict_of_openPoseSegmentIdx_dicts['face'], segColor='k', lineWidth=.5)

    matplotlib_artist_objs['skel_dottos'] = [ax3d.plot(thisTraj[0, 0:1], thisTraj[1, 0:1], thisTraj[2, 0:1],'k.', markersize=1)[0] for thisTraj in skel_trajectories]
    matplotlib_artist_objs['dlc_dottos'] = [ax3d.plot(thisTraj[0, 0:1], thisTraj[1, 0:1], thisTraj[2, 0:1],'b.', markersize=1)[0] for thisTraj in dlc_trajectories]
    
    numFrames = skel_fr_mar_dim.shape[0]
   



    mx = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,0])
    my = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,1])
    mz = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,2])

    axRange = 600#session.board.square_length * 10

    # Setting the axes properties
    ax3d.set_xlim3d([mx-axRange, mx+axRange])
    ax3d.set_ylim3d([my-axRange, my+axRange])
    ax3d.set_zlim3d([mz-axRange, mz+axRange])
    
    fig.suptitle("SessionID: {}, Frame: {} of {}".format(session.sessionID, startFrame, numFrames))

    ax3d.view_init(azim=azimuth, elev=elevation)
    


###   
###   
###   ███    ███  █████  ██   ██ ███████     ██    ██ ██ ██████  ███████  ██████       █████  ██   ██ ███████ ███████ 
###   ████  ████ ██   ██ ██  ██  ██          ██    ██ ██ ██   ██ ██      ██    ██     ██   ██  ██ ██  ██      ██      
###   ██ ████ ██ ███████ █████   █████       ██    ██ ██ ██   ██ █████   ██    ██     ███████   ███   █████   ███████ 
###   ██  ██  ██ ██   ██ ██  ██  ██           ██  ██  ██ ██   ██ ██      ██    ██     ██   ██  ██ ██  ██           ██ 
###   ██      ██ ██   ██ ██   ██ ███████       ████   ██ ██████  ███████  ██████      ██   ██ ██   ██ ███████ ███████ 
###                                                                                                                   
###                                                                                                                   
    

    syncedVidPathListAll = list(sorted(session.syncedVidPath.glob('*.mp4')))
    
    #remove a few vids, 6 is too many! NOTE - this is kinda hardcoded for the 20-07-2021 release video
    if session.sessionID == 'sesh_21-07-08_131030':
        useCams = [0,1,2,3]
    #     delTheseVids = [4,1]
    
    if useCams: #JSM NOTE _ This might not work at all lol 
        syncedVidPathList = [syncedVidPathListAll[camNum] for camNum in useCams]
        dlcData_nCams_nFrames_nImgPts_XYC = dlcData_nCams_nFrames_nImgPts_XYC[useCams, :, :, :]
        openPoseData_nCams_nFrames_nImgPts_XYC = openPoseData_nCams_nFrames_nImgPts_XYC[useCams, :, :, :]
    else:
        syncedVidPathList  = syncedVidPathListAll.copy()

    vidAxesList = []
    vidAristList = []
    vidCapObjList = []

    vidDLCArtistList = []
    vidOpenPoseArtistList = []
    
    vidAx_positions = []

    left = .45
    bottom = 0.05
    vidWidth = .38
    vidHeight = vidWidth
    widthScale = .6
    heightScale = 1.2

    vidAx_positions.append([
        left, 
        bottom, 
        vidWidth, 
        vidHeight])

    vidAx_positions.append([
        left+vidWidth*widthScale, 
        bottom, 
        vidWidth, 
        vidHeight])

    vidAx_positions.append([
        left, 
        bottom+vidHeight*heightScale, 
        vidWidth, 
        vidHeight])

    vidAx_positions.append([
        left+vidWidth*widthScale,
        bottom+vidHeight*heightScale, 
        vidWidth, 
        vidHeight])


    for vidSubplotNum, thisVidPath in enumerate(syncedVidPathList):
        #make subplot for figure (and set position)
        thisVidAxis = fig.add_subplot(
                                    position=vidAx_positions[vidSubplotNum], 
                                    label="Vid_{}".format(str(vidSubplotNum)),
                                    ) 

        thisVidAxis.set_axis_off()

        vidAxesList.append(thisVidAxis)

        #create video capture object
        vidCapObjList.append(cv2.VideoCapture(str(thisVidPath)))

        #create artist object for each video 
        success, image  = vidCapObjList[-1].read()

        if startFrame > 0:
            for fr in range(startFrame-1): #cycle through frames until you hit startFrame (there's probably a better way to do this?)
                success, image  = vidCapObjList[-1].read()
                assert success==True, "{} - failed to load an image".format(thisVidPath.stem) #make sure we have a frame
        vidAristList.append(plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))

        if useOpenPose:
            vidOpenPoseArtistList.append(plt.plot(
                                    openPoseData_nCams_nFrames_nImgPts_XYC[vidSubplotNum,startFrame,:,0], 
                                    openPoseData_nCams_nFrames_nImgPts_XYC[vidSubplotNum,startFrame,:,1],
                                    linestyle='none',
                                    marker = ',',
                                    color='w',
                                    markerfacecolor='none' ))
        

        if useDLC:
            vidDLCArtistList.append(plt.plot(
                                    dlcData_nCams_nFrames_nImgPts_XYC[vidSubplotNum,startFrame,:,0], 
                                    dlcData_nCams_nFrames_nImgPts_XYC[vidSubplotNum,startFrame,:,1],
                                    linestyle='none',
                                    marker = ',',
                                    color='w',
                                    markerfacecolor='none' ))
            


    # #slider
    # axControls = fig.add_subplot(2,1,2)
    # axControls.set_position([0.25, 0.01, 0.6, 0.05])
    # animSlider = Slider(
    #     ax=axControls,
    #     label="FrameNum",
    #     valmin=10,
    #     valmax=numFrames,
    #     valinit=10,
    #     orientation="horizontal"
    # )

    # Creating the Animation object
    line_animation = animation.FuncAnimation(fig, update_figure, range(startFrame,numFrames), fargs=(),
                                    interval=1, blit=False)


    
    if recordVid:
        with console.status('Saving video...'):
            Writer = animation.writers['ffmpeg']
            writer = Writer(fps=30, metadata=dict(artist='FreeMoCap'), bitrate=1800)
            vidSavePath = '{}_outVid.mp4'.format(str(session.sessionPath / session.sessionID))
            line_animation.save(vidSavePath, writer = writer)

 
    plt.pause(0.1)
    plt.draw()


    console.print(":sparkle: :skull: :sparkle:")


### 
###    
###    ███████  ██████  ██████  ███    ███  █████  ████████      ██████  ██████  ███████ ███    ██ ██████   ██████  ███████ ███████     ███████ ██   ██ ███████ ██      
###    ██      ██    ██ ██   ██ ████  ████ ██   ██    ██        ██    ██ ██   ██ ██      ████   ██ ██   ██ ██    ██ ██      ██          ██      ██  ██  ██      ██      
###    █████   ██    ██ ██████  ██ ████ ██ ███████    ██        ██    ██ ██████  █████   ██ ██  ██ ██████  ██    ██ ███████ █████       ███████ █████   █████   ██      
###    ██      ██    ██ ██   ██ ██  ██  ██ ██   ██    ██        ██    ██ ██      ██      ██  ██ ██ ██      ██    ██      ██ ██               ██ ██  ██  ██      ██      
###    ██       ██████  ██   ██ ██      ██ ██   ██    ██         ██████  ██      ███████ ██   ████ ██       ██████  ███████ ███████     ███████ ██   ██ ███████ ███████ 
###                                                                                                                                                                         
###                                                                                                                                                                         
def formatOpenPoseStickIndices():
    """
    generate dictionary of arrays, each containing the 'connect-the-dots' order to draw a given body segment
    
    returns:
    openPoseBodySegmentIds= a dictionary of arrays containing indices of individual body segments (Note, a lot of markerless mocap comp sci types like to say 'pose' instead of 'body'. They also use 'pose' to refer to camera 6 DoF position sometimes. Comp sci is frustrating like that lol)
    openPoseHandIds = a dictionary of arrays containing indices of individual hand segments, along with offset to know where to start in the 'skel_fr_mar_dim.shape[1]' part of the array
    dict_of_skel_lineColor = a dictionary of arrays, each containing the color (RGBA) to use for a given body segment
    """
    dict_of_openPoseSegmentIdx_dicts = dict()

    #make body dictionary
    openPoseBodySegmentIds = dict()
    openPoseBodySegmentIds['head'] = [17, 15, 0, 1,0, 16, 18, ]
    openPoseBodySegmentIds['spine'] = [1,8,5,1, 2, 12, 8, 9, 5, 1, 2, 8]
    openPoseBodySegmentIds['rArm'] = [1, 2, 3, 4, ]
    openPoseBodySegmentIds['lArm'] = [1, 5, 6, 7, ]
    openPoseBodySegmentIds['rLeg'] = [8, 9, 10, 11, 22, 23, 11, 24, ]
    openPoseBodySegmentIds['lLeg'] = [8,12, 13, 14, 19, 20, 14, 21,]
    dict_of_openPoseSegmentIdx_dicts['body'] = openPoseBodySegmentIds


    dict_of_skel_lineColor = dict()
    dict_of_skel_lineColor['head'] = np.append(humon_dark, 0.5)
    dict_of_skel_lineColor['spine'] = np.append(humon_dark, 1)
    dict_of_skel_lineColor['rArm'] = np.append(humon_red, 1)
    dict_of_skel_lineColor['lArm'] = np.append(humon_blue, 1)
    dict_of_skel_lineColor['rLeg'] = np.append(humon_red, 1)
    dict_of_skel_lineColor['lLeg'] = np.append(humon_blue, 1)


    # Make some handy maps ;D
    openPoseHandIds = dict()
    rHandIDstart = 25
    lHandIDstart = rHandIDstart + 21

    openPoseHandIds['thumb'] = np.array([0, 1, 2, 3, 4,  ]) 
    openPoseHandIds['index'] = np.array([0, 5, 6, 7, 8, ])
    openPoseHandIds['bird']= np.array([0, 9, 10, 11, 12, ])
    openPoseHandIds['ring']= np.array([0, 13, 14, 15, 16, ])
    openPoseHandIds['pinky'] = np.array([0, 17, 18, 19, 20, ])
    

    rHand_dict = copy.deepcopy(openPoseHandIds.copy()) #copy.deepcopy() is necessary to make sure the dicts are independent of each other
    lHand_dict = copy.deepcopy(rHand_dict)

    for key in rHand_dict: 
        rHand_dict[key] += rHandIDstart 
        lHand_dict[key] += lHandIDstart 

    dict_of_openPoseSegmentIdx_dicts['rHand'] = rHand_dict
    dict_of_openPoseSegmentIdx_dicts['lHand'] = lHand_dict

    
    #how to face --> :D <--
    openPoseFaceIDs = dict()
    faceIDStart = 67
    #define face parts
    openPoseFaceIDs['jaw'] = np.arange(0,16) + faceIDStart 
    openPoseFaceIDs['rBrow'] = np.arange(17,21) + faceIDStart
    openPoseFaceIDs['lBrow'] = np.arange(22,26) + faceIDStart
    openPoseFaceIDs['noseRidge'] = np.arange(27,30) + faceIDStart
    openPoseFaceIDs['noseBot'] = np.arange(31,35) + faceIDStart
    openPoseFaceIDs['rEye'] = np.concatenate((np.arange(36,41), [36])) + faceIDStart
    openPoseFaceIDs['lEye'] = np.concatenate((np.arange(42,47), [42])) + faceIDStart    
    openPoseFaceIDs['upperLip'] = np.concatenate((np.arange(48,54), np.flip(np.arange(60, 64)), [48])) + faceIDStart
    openPoseFaceIDs['lowerLip'] = np.concatenate(([60], np.arange(64,67), np.arange(54, 59), [48], [60])) + faceIDStart
    openPoseFaceIDs['rPupil'] = np.array([68]) + faceIDStart
    openPoseFaceIDs['lPupil'] = np.array([69]) + faceIDStart #nice

    dict_of_openPoseSegmentIdx_dicts['face'] = openPoseFaceIDs
    
    return dict_of_openPoseSegmentIdx_dicts, dict_of_skel_lineColor



if __name__ == '__main__':
    PlaySkeletonAnimation()
