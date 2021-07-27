
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

import matplotlib as mpl
import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as p3
import matplotlib.animation as animation
from matplotlib.widgets import Slider
import cv2 
from scipy.signal import savgol_filter

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
humon_blue = np.array([14, 90, 253])/255
humon_red = np.array([217, 61, 67])/255


def PlaySkeletonAnimation(
    session=None,
    vidType=1,
    startFrame=0,
    azimuth=-90,
    elevation=-61,
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

        #function to update the lines for each 3d body segment
        def update_3d_skel_segments(key, data_fr_mar_dim):       
            """ 
            updates the Artist of each body segment with the current frame data.
            """    
            try:   
                dict_of_segments_idxs = dict_of_openPoseSegmentIdx_dicts[key]
            except: 
                dict_of_segments_idxs = dict_of_dlcSegmentIdx_dicts[key]

            dict_of_artists = matplotlib_artist_objs[key] 

            for thisItem in dict_of_segments_idxs.items():
                segName = thisItem[0]
                segArtist = dict_of_artists[segName]
                segArtist.set_data((data_fr_mar_dim[frameNum, dict_of_segments_idxs[segName], 0], data_fr_mar_dim[frameNum, dict_of_segments_idxs[segName], 1]))
                segArtist.set_3d_properties(data_fr_mar_dim[frameNum, dict_of_segments_idxs[segName], 2])                
            
        update_3d_skel_segments('body', skel_fr_mar_dim)
        update_3d_skel_segments('rHand', skel_fr_mar_dim)
        update_3d_skel_segments('lHand', skel_fr_mar_dim)
        update_3d_skel_segments('face', skel_fr_mar_dim)

        update_3d_skel_segments('pinkBall', dlc_fr_mar_dim)
        update_3d_skel_segments('redBall', dlc_fr_mar_dim)
        update_3d_skel_segments('greenBall', dlc_fr_mar_dim)
        update_3d_skel_segments('wobbleBoard', dlc_fr_mar_dim)
        update_3d_skel_segments('wobbleWheel', dlc_fr_mar_dim)

        for bb in range(3):
            thisTailArtist = matplotlib_artist_objs['ball_tails'][bb]
           
            thisTailArtist.set_data((dlc_trajectories[bb][frameNum-ballTailLen:frameNum+1, 0], 
                                    dlc_trajectories[bb][frameNum-ballTailLen:frameNum+1, 1])) 

            thisTailArtist.set_3d_properties(dlc_trajectories[bb][frameNum-ballTailLen:frameNum+1, 2]) 


        #Plots the dots!
        #openpose data
        marNum = -1
        for thisSkelDotto, thisTraj in zip(skel_dottos,skel_trajectories):
            marNum+=1
            # NOTE: there is no .set_data() for 3 dim data...
            thisSkelDotto.set_data(thisTraj[ frameNum, 0:2])
            thisSkelDotto.set_3d_properties(thisTraj[ frameNum, 2])

        #dlc data
        marNum = -1
        for thisDotto, thisTraj in zip(dlc_dottos,dlc_trajectories):
            marNum+=1
            # NOTE: there is no .set_data() for 3 dim data...
            thisDotto.set_data(thisTraj[ frameNum, 0:2])
            thisDotto.set_3d_properties(thisTraj[ frameNum, 2])
        
        # function to update the lines for each body segment
        def update_2d_skel_segments(vidNum,key):       
            """ 
            updates the Artist of each body segment with the current frame data.
            """       
            dict_of_segments_idxs = dict_of_openPoseSegmentIdx_dicts[key]
            dict_of_artists = thisVidOpenPoseArtist_dict[key] 


            for thisItem in dict_of_segments_idxs.items():
                segName = thisItem[0]
                segArtist = dict_of_artists[segName]

                xData = openPoseData_nCams_nFrames_nImgPts_XYC[vidNum, frameNum, dict_of_segments_idxs[segName],0]
                yData = openPoseData_nCams_nFrames_nImgPts_XYC[vidNum, frameNum, dict_of_segments_idxs[segName],1]

                xDataMasked = np.ma.masked_array(xData, mask=(xData==0))
                yDataMasked = np.ma.masked_array(yData, mask=(xData==0))
                segArtist.set_data(xDataMasked,yDataMasked)
                
            

        vidNum = -1
        for thisVidArtist, thisVidDLCArtist, thisVidOpenPoseArtist_dict in zip(vidAristList, vidDLCArtistList, list_of_vidOpenPoseArtistdicts):
            vidNum +=1
            vidCapObjList[vidNum].set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            success, image = vidCapObjList[vidNum].read()
            if success:
                thisVidArtist.set_array(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                vidCapObjList[vidNum].set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, image = vidCapObjList[vidNum].read()

            thisVidDLCArtist[0].set_data(  dlcData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum,:,0], 
                                    dlcData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum,:,1],)

            update_2d_skel_segments(vidNum,'body')
            update_2d_skel_segments(vidNum,'rHand')
            update_2d_skel_segments(vidNum,'lHand')
            update_2d_skel_segments(vidNum,'face')
            # thisVidOpenPoseArtist_dict[0].set_data(  openPoseData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum,:,0], 
            #                         openPoseData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum,:,1],)

        #shift timeseries xlims along with the frameNum
        xTimeSeriesAx.set_xlim([(frameNum/fps)-timeRange, (frameNum/fps)+timeRange])
        yTimeSeriesAx.set_xlim([(frameNum/fps)-timeRange, (frameNum/fps)+timeRange])
        for thisArtistKey in xCurrTimeArtists:

            xCurrTimeArtists[thisArtistKey][0].set_xdata(frameNum/fps) 
            yCurrTimeArtists[thisArtistKey][0].set_xdata(frameNum/fps) 
            if not thisArtistKey == 'blackLine':
                xCurrTimeArtists[thisArtistKey][0].set_ydata(xCurrTimeYdata[thisArtistKey][frameNum] ) 
                yCurrTimeArtists[thisArtistKey][0].set_ydata(yCurrTimeYdata[thisArtistKey][frameNum] ) 
                
        
        # fig.suptitle("nSessionID: {}, Frame: {} of {}".format(session.sessionID, frameNum, numFrames), fontsize=10)
        # animSlider.set_val(val=frameNum)

####  
####   ██████ ██████  ███████  █████  ████████ ███████     ███████ ██  ██████  ██    ██ ██████  ███████ 
####  ██      ██   ██ ██      ██   ██    ██    ██          ██      ██ ██       ██    ██ ██   ██ ██      
####  ██      ██████  █████   ███████    ██    █████       █████   ██ ██   ███ ██    ██ ██████  █████   
####  ██      ██   ██ ██      ██   ██    ██    ██          ██      ██ ██    ██ ██    ██ ██   ██ ██      
####   ██████ ██   ██ ███████ ██   ██    ██    ███████     ██      ██  ██████   ██████  ██   ██ ███████ 
####                                                                                                    
    

    fig = plt.figure(dpi=200)
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
    ax3d.set_position([-.065, .35, .7, .7]) # [left, bottom, width, height])
    ax3d.set_xticklabels([])
    ax3d.set_yticklabels([])
    ax3d.set_zticklabels([])

    # ax3d.set_xlabel('X')
    # ax3d.set_ylabel('Y')
    # ax3d.set_zlabel('Z')
    # ax3d.set_axis_off()


    ax3d.tick_params(length=0) # WHY DOESNT THIS WORK? I HATE THOSE TICK MARKS >:(
    
    try:
        skel_fr_mar_dim = np.load(session.dataArrayPath / 'openPoseSkel_3d.npy')
        openPoseData_nCams_nFrames_nImgPts_XYC = np.load(session.dataArrayPath / 'openPoseData_2d.npy')
    except:
        console.warning('No openPose data found.  This iteration requires OpenPose data')

    # smoothThese = np.arange(67, skel_fr_mar_dim.shape[1])
    smoothThese = np.arange(0, skel_fr_mar_dim.shape[1])

    for mm in smoothThese:
        if mm > 24 and mm < 67: #don't smooth the hands, or they disappear! :O
            pass
        else:
            for dim in range(skel_fr_mar_dim.shape[2]):
                skel_fr_mar_dim[:,mm,dim] = savgol_filter(skel_fr_mar_dim[:,mm,dim], 5, 3)

    figure_data = dict()

    skel_trajectories = [skel_fr_mar_dim[:,markerNum,:] for markerNum in range(skel_fr_mar_dim.shape[1])]
    figure_data['skel_trajectories|mar|fr_dim'] = skel_trajectories
    figure_data['skel_fr_mar_dim'] = skel_fr_mar_dim
    dict_of_openPoseSegmentIdx_dicts, dict_of_skel_lineColor = formatOpenPoseStickIndices() #these will help us draw body and hands stick figures

    if useDLC:
        dlc_fr_mar_dim = np.load(session.dataArrayPath / "deepLabCut_3d.npy")
        dlcData_nCams_nFrames_nImgPts_XYC = np.load(session.dataArrayPath / "deepLabCutData_2d.npy")
        
        for mm in range(dlc_fr_mar_dim.shape[1]):
            for dim in range(dlc_fr_mar_dim.shape[2]):
                dlc_fr_mar_dim[:,mm,dim] = savgol_filter(dlc_fr_mar_dim[:,mm,dim], 11, 3)

        ballTailLen = 6
        if ballTailLen > startFrame:
            startFrame = ballTailLen+1 #gotta do this, or the tail will index negative frames (without requiring annoying checks later)
    
    dlc_trajectories = [dlc_fr_mar_dim[:,markerNum,:] for markerNum in range(dlc_fr_mar_dim.shape[1])]    
    figure_data['dlc_trajectories|mar|fr_dim'] = dlc_trajectories
    figure_data['dlc_fr_mar_dim'] = dlc_fr_mar_dim

    
    
    
    def build_3d_segment_artist_dict(data_fr_mar_dim,
                                     dict_of_list_of_segment_idxs, 
                                     segColor = 'k', 
                                     lineWidth = 1, 
                                     lineStyle = '-', 
                                     markerType = None, 
                                     marSize = 12, 
                                     markerEdgeColor = 'k',):       
        """ 
        Builds a dictionary of line artists for each 3D body segment.
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

            if isinstance(segName, str):
                idxsOG = dict_of_list_of_segment_idxs[segName]
            else:
                idxsOG

            if isinstance(idxsOG, int) or isinstance(idxsOG, float): 
                idxs = [idxsOG]
            elif isinstance(idxsOG, dict):
                idxs = idxsOG[0]
            else:
                idxs = idxsOG.copy()


            dict_of_artist_objects[segName]  = ax3d.plot(
                                                    data_fr_mar_dim[startFrame, idxs ,0], 
                                                    data_fr_mar_dim[startFrame, idxs ,1], 
                                                    data_fr_mar_dim[startFrame, idxs ,2],
                                                    linestyle=lineStyle,
                                                    linewidth=lineWidth,
                                                    markerSize = marSize,
                                                    marker = markerType,
                                                    color = thisRGBA,
                                                    markeredgecolor = markerEdgeColor,
                                                    )[0]
        return dict_of_artist_objects

    

    matplotlib_artist_objs = dict()
    matplotlib_artist_objs['body'] = build_3d_segment_artist_dict(skel_fr_mar_dim, dict_of_openPoseSegmentIdx_dicts['body'], segColor = dict_of_skel_lineColor)
    matplotlib_artist_objs['rHand'] = build_3d_segment_artist_dict(skel_fr_mar_dim, dict_of_openPoseSegmentIdx_dicts['rHand'], segColor=np.append(humon_red, 1), markerType='.', markerEdgeColor = humon_red, lineWidth=1, marSize = 2)
    matplotlib_artist_objs['lHand'] = build_3d_segment_artist_dict(skel_fr_mar_dim, dict_of_openPoseSegmentIdx_dicts['lHand'], segColor=np.append(humon_blue, 1), markerType='.', markerEdgeColor = humon_blue, lineWidth=1, marSize = 2)
    matplotlib_artist_objs['face'] = build_3d_segment_artist_dict(skel_fr_mar_dim, dict_of_openPoseSegmentIdx_dicts['face'], segColor='k', lineWidth=.5)
    
    dict_of_dlcSegmentIdx_dicts = dict()
    dict_of_dlcSegmentIdx_dicts['pinkBall'] = {'pinkBall': [0]}
    dict_of_dlcSegmentIdx_dicts['greenBall'] = {'greenBall': [1]}
    dict_of_dlcSegmentIdx_dicts['redBall'] = {'redBall': [2]}
    dict_of_dlcSegmentIdx_dicts['wobbleBoard'] = {'wobbleboard':[3,4,5,6,3,7,5,4,7,6]}
    dict_of_dlcSegmentIdx_dicts['wobbleWheel'] = {'wobbleWheel':[8,9]}
    
    ballColor = ['darkviolet', 'forestgreen', 'xkcd:goldenrod']
    matplotlib_artist_objs['pinkBall'] = build_3d_segment_artist_dict(dlc_fr_mar_dim, dict_of_dlcSegmentIdx_dicts['pinkBall'], segColor=ballColor[0], markerType = 'o', marSize = 6, markerEdgeColor = 'indigo')
    matplotlib_artist_objs['redBall'] = build_3d_segment_artist_dict(dlc_fr_mar_dim, dict_of_dlcSegmentIdx_dicts['redBall'], segColor=ballColor[2], markerType = 'o', marSize = 6, markerEdgeColor ='orangered')
    matplotlib_artist_objs['greenBall'] = build_3d_segment_artist_dict(dlc_fr_mar_dim, dict_of_dlcSegmentIdx_dicts['greenBall'], segColor=ballColor[1], markerType = 'o', marSize = 6, markerEdgeColor ='darkgreen')

    matplotlib_artist_objs['wobbleBoard'] = build_3d_segment_artist_dict(dlc_fr_mar_dim, dict_of_dlcSegmentIdx_dicts['wobbleBoard'], segColor='k', lineWidth=1)
    matplotlib_artist_objs['wobbleWheel'] = build_3d_segment_artist_dict(dlc_fr_mar_dim, dict_of_dlcSegmentIdx_dicts['wobbleWheel'], segColor='k', lineWidth=1)

    skel_dottos = []
    for mm in range(67): #getcher dottos off my face!
        thisTraj = skel_fr_mar_dim[:, mm, :]
        if mm==15:
            col = 'r'
            markerSize = 2
        elif mm == 16:
            col = 'b'
            markerSize = 2
        else:
            col = 'k'
            markerSize = 1

        thisDotto =ax3d.plot(thisTraj[0, 0:1], thisTraj[1, 0:1], thisTraj[2, 0:1][0],'.', markersize=markerSize, color = col)
        skel_dottos.append(thisDotto[0])

    matplotlib_artist_objs['skel_dottos'] = skel_dottos

    matplotlib_artist_objs['dlc_dottos'] = [ax3d.plot(thisTraj[0, 0:1], thisTraj[1, 0:1], thisTraj[2, 0:1],'b.', markersize=1)[0] for thisTraj in dlc_trajectories]

    matplotlib_artist_objs['ball_tails'] = [ax3d.plot( 
                                            dlc_trajectories[bb][startFrame-ballTailLen:startFrame, 0],
                                            dlc_trajectories[bb][startFrame-ballTailLen:startFrame, 1],
                                            dlc_trajectories[bb][startFrame-ballTailLen:startFrame, 2],
                                            '-', color=ballColor[bb])[0] for bb in range(3)]
    

    numFrames = skel_fr_mar_dim.shape[0]
   



    mx = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,0])
    my = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,1])
    mz = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,2])

    # groundX = np.arange(mx-100,mx+100)
    # groundZ = np.arange(my-100,my+100)
    # groundXX, groundZZ = np.meshgrid(groundX, groundZ)
    # groundYY = np.zeros_like(groundXX)
    # groundMesh = ax3d.plot_surface(groundXX, groundZZ, groundYY, color='k', alpha=.5)

    axRange = 500#session.board.square_length * 10

    # Setting the axes properties
    ax3d.set_xlim3d([mx-axRange, mx+axRange])
    ax3d.set_ylim3d([my-axRange, my+axRange])
    ax3d.set_zlim3d([mz-axRange-1600, mz+axRange-1600])
    
    fig.suptitle("-The FreeMoCap Project-", fontsize=14)

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

    list_of_vidOpenPoseArtistdicts = []
    vidDLCArtistList = []
    
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

    def build_2d_segment_artist_dict(vidNum, data_nCams_nFrames_nImgPts_XYC, dict_of_list_of_segment_idxs, segColor = 'k', lineWidth = 1, lineStyle = '-'):       
        """ 
        Builds a dictionary of line artists for each body 2d segment.
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
                thisRGBA = segColor[segName].copy()
                thisRGBA[-1] = .75
            elif isinstance(segColor, list):
                try:
                    thisRGBA = segColor[segNum]
                except:
                    print('Not enough colors provided, using Black instead')
                    thisRGBA = 'k'
            else:
                thisRGBA = 'k'

            xData = data_nCams_nFrames_nImgPts_XYC[vidNum, startFrame, dict_of_list_of_segment_idxs[segName],0]
            yData = data_nCams_nFrames_nImgPts_XYC[vidNum, startFrame, dict_of_list_of_segment_idxs[segName],1]

            # #make NaN's invisible (i thought they already would be but???!!!!)
            # thisRGBAall = np.tile(thisRGBA,(len(xData),1))
            # thisRGBAall[np.isnan(xData),3] = 0
            
            xDataMasked  = np.ma.masked_where(xData, np.isnan(xData))
            yDataMasked  = np.ma.masked_where(yData, np.isnan(yData))

            dict_of_artist_objects[segName]  = thisVidAxis.plot(
                                                    xDataMasked,
                                                    yDataMasked,
                                                    linestyle=lineStyle,
                                                    linewidth=lineWidth,
                                                    color = thisRGBA,
                                                    )[0]
        return dict_of_artist_objects


    for vidSubplotNum, thisVidPath in enumerate(syncedVidPathList):
        #make subplot for figure (and set position)
        thisVidAxis = fig.add_subplot(
                                    position=vidAx_positions[vidSubplotNum], 
                                    label="Vid_{}".format(str(vidSubplotNum)),
                                    ) 

        thisVidAxis.set_axis_off()

        vidAxesList.append(thisVidAxis)

        #create video capture object
        thisVidCap = cv2.VideoCapture(str(thisVidPath))
        

        #create artist object for each video 
        success, image  = thisVidCap.read()

        assert success==True, "{} - failed to load an image".format(thisVidPath.stem) #make sure we have a frame

        vidAristList.append(thisVidAxis.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
        vidCapObjList.append(thisVidCap)



        if useOpenPose:
            vidOpenPoseArtist_dict = dict()            
            vidOpenPoseArtist_dict['body'] = build_2d_segment_artist_dict(vidSubplotNum, openPoseData_nCams_nFrames_nImgPts_XYC, dict_of_openPoseSegmentIdx_dicts['body'], segColor = dict_of_skel_lineColor)
            vidOpenPoseArtist_dict['rHand'] = build_2d_segment_artist_dict(vidSubplotNum, openPoseData_nCams_nFrames_nImgPts_XYC, dict_of_openPoseSegmentIdx_dicts['rHand'], segColor=np.append(humon_red, .75), lineWidth=.5)
            vidOpenPoseArtist_dict['lHand'] = build_2d_segment_artist_dict(vidSubplotNum, openPoseData_nCams_nFrames_nImgPts_XYC, dict_of_openPoseSegmentIdx_dicts['lHand'], segColor=np.append(humon_blue, .75), lineWidth=.5)
            vidOpenPoseArtist_dict['face'] = build_2d_segment_artist_dict(vidSubplotNum, openPoseData_nCams_nFrames_nImgPts_XYC, dict_of_openPoseSegmentIdx_dicts['face'], segColor = np.array([1.,1.,1.,1]), lineWidth=.25)
            list_of_vidOpenPoseArtistdicts.append(vidOpenPoseArtist_dict)

        if useDLC:
            
            vidDLCArtistList.append(thisVidAxis.plot(
                                    dlcData_nCams_nFrames_nImgPts_XYC[vidSubplotNum,startFrame,:,0], 
                                    dlcData_nCams_nFrames_nImgPts_XYC[vidSubplotNum,startFrame,:,1],
                                    linestyle='none',
                                    marker = '.',
                                    markersize = 1,
                                    color='w',
                                    markerfacecolor='none' ))
    ###               
    ###   
    ###   ███    ███  █████  ██   ██ ███████     ██      ██ ███    ██ ███████     ██████  ██       ██████  ████████      █████  ██   ██ ███████ ███████ 
    ###   ████  ████ ██   ██ ██  ██  ██          ██      ██ ████   ██ ██          ██   ██ ██      ██    ██    ██        ██   ██  ██ ██  ██      ██      
    ###   ██ ████ ██ ███████ █████   █████       ██      ██ ██ ██  ██ █████       ██████  ██      ██    ██    ██        ███████   ███   █████   ███████ 
    ###   ██  ██  ██ ██   ██ ██  ██  ██          ██      ██ ██  ██ ██ ██          ██      ██      ██    ██    ██        ██   ██  ██ ██  ██           ██ 
    ###   ██      ██ ██   ██ ██   ██ ███████     ███████ ██ ██   ████ ███████     ██      ███████  ██████     ██        ██   ██ ██   ██ ███████ ███████ 
    ###                                                                                                                                                 
    ###                                                                                                                                                 


    fps=30 #NOTE - This should be saved in the session Class some how
    time = np.arange(0, numFrames)/fps
    
    rHandX = skel_trajectories[4][:,0]
    rHandY = -skel_trajectories[4][:,1]
    lHandX = skel_trajectories[7][:,0]
    lHandY = -skel_trajectories[7][:,1]

    ballX_1 = dlc_trajectories[2][:lHandX.shape[0],0] #NOTE - Why tf aren't these the same length already?!?
    ballY_1 = -dlc_trajectories[2][:lHandX.shape[0],1]
    ballLineColor_1 = ballColor[2]

    # ballX_2 = dlc_trajectories[1][:lHandX.shape[0],0] #NOTE - Why tf aren't these the same length already?!?
    # ballY_2 = -dlc_trajectories[1][:lHandX.shape[0],1]
    # ballLineColor_2 = ballColor[1]

    # ballX_3 = dlc_trajectories[0][:lHandX.shape[0],0] #NOTE - Why tf aren't these the same length already?!?
    # ballY_3 = -dlc_trajectories[0][:lHandX.shape[0],1]
    # ballLineColor_3 = ballColor[0]


    yTimeSeriesAx = fig.add_subplot(position=[.07, .25, .45, .18])
    yTimeSeriesAx.set_title('Hand and Juggling Ball Position vs Time', fontsize = 7, pad=2)

    yTimeSeriesAx.plot(time, ballY_1, color=ballLineColor_1, alpha=.99, linewidth=1.5, label='Juggling Ball')    
    # yTimeSeriesAx.plot(time, ballY_2, color=ballLineColor_2, alpha=.99, linewidth=1.5, label='Juggling Ball')    
    # yTimeSeriesAx.plot(time, ballY_3, color=ballLineColor_3, alpha=.99, linewidth=1.5, label='Juggling Ball')    
    yTimeSeriesAx.plot(time, rHandY, color=humon_red, linewidth=.75, label='Right Hand')
    yTimeSeriesAx.plot(time, lHandY, color=humon_blue, linewidth=.75, label='Left Hand')
    
    

    ylimRange = 300
    yCurrTimeArtists = dict()
    yCurrTimeYdata = dict()
    yCurrTimeArtists['blackLine']  = yTimeSeriesAx.plot([startFrame/fps, startFrame/fps], [-ylimRange, ylimRange*2], color='k', linewidth=1)
    yCurrTimeArtists['JugglingBall_1']  = yTimeSeriesAx.plot([startFrame/fps], [ballY_1[startFrame]], color=ballLineColor_1, markeredgecolor = 'orangered',marker='o', markersize=5)
    yCurrTimeYdata['JugglingBall_1'] = ballY_1
    # yCurrTimeArtists['JugglingBall_2']  = yTimeSeriesAx.plot([startFrame/fps], [ballY_2[startFrame]], color=ballLineColor_2, markeredgecolor = 'darkgreen',marker='o', markersize=5)
    # yCurrTimeYdata['JugglingBall_2'] = ballY_2
    # yCurrTimeArtists['JugglingBall_3']  = yTimeSeriesAx.plot([startFrame/fps], [ballY_3[startFrame]], color=ballLineColor_3, markeredgecolor = 'violet',marker='o', markersize=5)
    # yCurrTimeYdata['JugglingBall_3'] = ballY_3

    yCurrTimeArtists['rHandDot']  = yTimeSeriesAx.plot([startFrame/fps], [rHandY[startFrame]], markeredgecolor=humon_red, markerfacecolor = 'k',marker='o', markersize=3)
    yCurrTimeYdata['rHandDot'] = rHandY
    yCurrTimeArtists['lHandDot']  = yTimeSeriesAx.plot([startFrame/fps], [lHandY[startFrame]], markeredgecolor=humon_blue, markerfacecolor = 'k', marker='o', markersize=3)
    yCurrTimeYdata['lHandDot'] = lHandY



    yTimeSeriesAx.tick_params(labelsize=6, direction='in', width=.5)
    yTimeSeriesAx.tick_params( pad=2)
    
    timeRange = 3
    yTimeSeriesAx.set_ylabel('Vertical (mm)', fontsize=7, labelpad=4)
    yTimeSeriesAx.set_ylim([-150, 600])
    yTimeSeriesAx.set_xlim([(startFrame/fps)-timeRange, (startFrame/fps)+timeRange])

    

    for axis in ['top','bottom','left','right']:
        yTimeSeriesAx.spines[axis].set_linewidth(0.5)



    yTimeSeriesAx.legend(loc='upper left', fontsize=6)



    xTimeSeriesAx = fig.add_subplot(position=[.07, 0.065, .45, .18])
    
    xTimeSeriesAx.plot(time, ballX_1, color=ballLineColor_1, alpha=.99, linewidth=1.25, label='Juggling Ball')    
    # xTimeSeriesAx.plot(time, ballX_2, color=ballLineColor_2, alpha=.99, linewidth=1.25, label='Juggling Ball')    
    # xTimeSeriesAx.plot(time, ballX_3, color=ballLineColor_3, alpha=.99, linewidth=1.25, label='Juggling Ball')    
    xTimeSeriesAx.plot(time, rHandX, color=humon_red, linewidth=.75, label='Right Hand')
    xTimeSeriesAx.plot(time, lHandX, color=humon_blue, linewidth=.75, label='Left Hand')
    

    ylimRange = 300
    xCurrTimeArtists = dict()
    xCurrTimeYdata = dict()
    xCurrTimeArtists['blackLine']  = xTimeSeriesAx.plot([startFrame/fps, startFrame/fps], [-ylimRange, ylimRange], color='k', linewidth=1)
    xCurrTimeArtists['JugglingBall_1']  = xTimeSeriesAx.plot([startFrame/fps], [ballX_1[startFrame]], color=ballLineColor_1, markeredgecolor = 'orangered',marker='o', markersize=5)
    xCurrTimeYdata['JugglingBall_1'] = ballX_1
    # xCurrTimeArtists['JugglingBall_2']  = xTimeSeriesAx.plot([startFrame/fps], [ballX_1[startFrame]], color=ballLineColor_2, markeredgecolor = 'darkgreen',marker='o', markersize=5)
    # xCurrTimeYdata['JugglingBall_2'] = ballX_2
    # xCurrTimeArtists['JugglingBall_3']  = xTimeSeriesAx.plot([startFrame/fps], [ballX_1[startFrame]], color=ballLineColor_3, markeredgecolor = 'indigo',marker='o', markersize=5)
    # xCurrTimeYdata['JugglingBall_3'] = ballX_3
    xCurrTimeArtists['rHandDot']  = xTimeSeriesAx.plot([startFrame/fps], [rHandX[startFrame]], markeredgecolor=humon_red, markerfacecolor = 'k',marker='o', markersize=3)
    xCurrTimeYdata['rHandDot'] = rHandX
    xCurrTimeArtists['lHandDot']  = xTimeSeriesAx.plot([startFrame/fps], [lHandX[startFrame]], markeredgecolor=humon_blue, markerfacecolor = 'k', marker='o', markersize=3)
    xCurrTimeYdata['lHandDot'] = lHandX



    xTimeSeriesAx.tick_params(labelsize=6, direction='in', width=.5)
    xTimeSeriesAx.tick_params( pad=2)
    
    xTimeSeriesAx.set_ylabel('Left/Right (mm)', fontsize=7, labelpad=1)
    xTimeSeriesAx.set_xlabel('Time(sec)', fontsize=8, labelpad=0)

    xTimeSeriesAx.set_ylim([-ylimRange, ylimRange])

    xTimeSeriesAx.set_xlim([(startFrame/fps)-timeRange, (startFrame/fps)+timeRange])

    
    for axis in ['top','bottom','left','right']:
        xTimeSeriesAx.spines[axis].set_linewidth(0.5)



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

    thisVidAxis.text(-565,1440, 'Music - artist: Neon Exdeath, song: Meowmaline, album: Jewel Tones',color=humon_green, fontsize=6)
    thisVidAxis.text(-565,1480, 'Code - github.com/jonmatthis/freemocap || jonmatthis.com/freemocap',color=humon_green, fontsize=6)

    logoAx = fig.add_subplot(position=[.9, .9, .1, .1])
    logoIm = cv2.imread(r"C:\Users\jonma\Downloads\freemocap-logo-border-2.png")
    logoAx.imshow(cv2.cvtColor(logoIm, cv2.COLOR_BGR2RGB))
    logoAx.axis('off')
    

    # Creating the Animation object
    line_animation = animation.FuncAnimation(fig, update_figure, range(startFrame,numFrames), fargs=(),
                                    interval=1, blit=False)


    
    if recordVid:
        vidSavePath = '{}_outVid.mp4'.format(str(session.sessionPath / session.sessionID))
        with console.status('Saving video - {}'.format(vidSavePath)):
            Writer = animation.writers['ffmpeg']
            writer = Writer(fps=30, metadata=dict(artist='FreeMoCap'))#, bitrate=1800)
            line_animation.save(vidSavePath, writer = writer)
            # Writer = animation.FFMpegWriter(fps=30, metadata=dict(artist='FreeMoCap', comment=session.sessionID), bitrate=1800)
            # vidSavePath = '{}_outVid.mp4'.format(str(session.sessionPath / session.sessionID))
            # Writer.saving(fig = fig, outfile=vidSavePath, dpi=150)

 
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
