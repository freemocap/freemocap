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
import moviepy.editor as mp

import os
import copy
from pathlib import Path
import time

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
    elevation=-70,
    useOpenPose=True,
    useMediaPipe=False,
    useDLC=False,
    recordVid = True,
    showAnimation =True,
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
        
        if useOpenPose:
            op_skel_dottos = matplotlib_artist_objs['op_skel_dottos'] 
            op_skel_trajectories = figure_data['openPose_skel_trajectories|mar|fr_dim']

        if useMediaPipe:
            mp_skel_dottos = matplotlib_artist_objs['mp_skel_dottos'] 
            mp_skel_trajectories = figure_data['mediaPipe_skel_trajectories|mar|fr_dim']

        charuco_dottos = matplotlib_artist_objs['charuco_dottos'] 
        charuco_trajectories = figure_data['charuco_trajectories|mar|fr_dim']

        if useDLC:
            dlc_dottos = matplotlib_artist_objs['dlc_dottos'] 
            dlc_trajectories = figure_data['dlc_trajectories|mar|fr_dim']

        #function to update the lines for each 3d body segment
        def update_3d_skel_segments(key, data_fr_mar_xyz):       
            """ 
            updates the Artist of each body segment with the current frame data.
            """    
            split = key.split('_')

            if split[0] == 'op':
                dict_of_segments_idxs = dict_of_openPoseSegmentIdx_dicts[key]
            if split[0] == 'mp':
                dict_of_segments_idxs = dict_of_mediaPipeSegmentIdx_dicts[key]
            elif split[0] == 'dlc':
                dict_of_segments_idxs = dict_of_dlcSegmentIdx_dicts[key]

            try:
                dict_of_artists = matplotlib_artist_objs[key] 
            except:
                print('KeyError:', key)
                

            for thisItem in dict_of_segments_idxs.items():
                segName = thisItem[0]
                segArtist = dict_of_artists[segName]
                segArtist.set_data((data_fr_mar_xyz[frameNum, dict_of_segments_idxs[segName], 0], data_fr_mar_xyz[frameNum, dict_of_segments_idxs[segName], 1]))
                segArtist.set_3d_properties(data_fr_mar_xyz[frameNum, dict_of_segments_idxs[segName], 2])                

        if useOpenPose:    
            update_3d_skel_segments('op_body', openPose_skel_fr_mar_xyz)
            update_3d_skel_segments('op_rHand', openPose_skel_fr_mar_xyz)
            update_3d_skel_segments('op_lHand', openPose_skel_fr_mar_xyz)
            update_3d_skel_segments('op_face', openPose_skel_fr_mar_xyz)

        if useMediaPipe:
            update_3d_skel_segments('mp_body', mediaPipe_skel_fr_mar_xyz)
            update_3d_skel_segments('mp_rHand', mediaPipe_skel_fr_mar_xyz)
            update_3d_skel_segments('mp_lHand', mediaPipe_skel_fr_mar_xyz)

        if useDLC:
            update_3d_skel_segments('dlc_pinkBall', dlc_fr_mar_xyz)
            update_3d_skel_segments('dlc_redBall', dlc_fr_mar_xyz)
            update_3d_skel_segments('dlc_greenBall', dlc_fr_mar_xyz)
            update_3d_skel_segments('dlc_wobbleBoard', dlc_fr_mar_xyz)
            update_3d_skel_segments('dlc_wobbleWheel', dlc_fr_mar_xyz)

            for bb in range(3):
                thisTailArtist = matplotlib_artist_objs['ball_tails'][bb]
            
                thisTailArtist.set_data((dlc_trajectories[bb][frameNum-ballTailLen:frameNum+1, 0], 
                                        dlc_trajectories[bb][frameNum-ballTailLen:frameNum+1, 1])) 

                thisTailArtist.set_3d_properties(dlc_trajectories[bb][frameNum-ballTailLen:frameNum+1, 2]) 
            #dlc data
            marNum = -1
            for thisDotto, thisTraj in zip(dlc_dottos,dlc_trajectories):
                marNum+=1
                # NOTE: there is no .set_data() for 3 dim data...
                thisDotto.set_data(thisTraj[ frameNum, 0:2])
                thisDotto.set_3d_properties(thisTraj[ frameNum, 2])

        #Plots the dots!
        #openpose data
        if useOpenPose:
            marNum = -1
            for thisSkelDotto, thisTraj in zip(op_skel_dottos,op_skel_trajectories):
                marNum+=1
                # NOTE: there is no .set_data() for 3 dim data...
                thisSkelDotto.set_data(thisTraj[ frameNum, 0:2])
                thisSkelDotto.set_3d_properties(thisTraj[ frameNum, 2])
        
        #mediapipe data
        if useMediaPipe:
            marNum = -1
            for thisSkelDotto, thisTraj in zip(mp_skel_dottos,mp_skel_trajectories):
                marNum+=1
                # NOTE: there is no .set_data() for 3 dim data...
                thisSkelDotto.set_data(thisTraj[ frameNum, 0:2])
                thisSkelDotto.set_3d_properties(thisTraj[ frameNum, 2])



        #charuco data        
        for thisDotto, thisTraj in zip(charuco_dottos,charuco_trajectories):

            if frameNum<charuco_trajectories[0].shape[0]:
                thisDotto.set_data(thisTraj[ frameNum, 0:2])
                thisDotto.set_3d_properties(thisTraj[ frameNum, 2])
            else:
                thisDotto.set_color('none')



        
        # function to update the lines for each body segment
        def update_2d_skel_segments(vidNum,key):       
            """ 
            updates the Artist of each body segment with the current frame data.
            """       
            split = key.split('_')
            if split[0] == 'op':
                dict_of_segments_idxs = dict_of_openPoseSegmentIdx_dicts[key]
                dict_of_artists = thisVidOpenPoseArtist_dict[key] 
            elif split[0] == 'mp':
                dict_of_segments_idxs = dict_of_mediaPipeSegmentIdx_dicts[key]
                dict_of_artists = thisVidMediaPipeArtist_dict[key] 


            for thisItem in dict_of_segments_idxs.items():
                segName = thisItem[0]
                segArtist = dict_of_artists[segName]
    
                if split[0] == 'op':
                    xData = openPose_nCams_nFrames_nImgPts_XYC[vidNum, frameNum, dict_of_segments_idxs[segName],0]
                    yData = openPose_nCams_nFrames_nImgPts_XYC[vidNum, frameNum, dict_of_segments_idxs[segName],1]
                elif split[0] == 'mp':
                    xData = mediaPipe_nCams_nFrames_nImgPts_XYC[vidNum, frameNum, dict_of_segments_idxs[segName],0]
                    yData = mediaPipe_nCams_nFrames_nImgPts_XYC[vidNum, frameNum, dict_of_segments_idxs[segName],1]

                xDataMasked = np.ma.masked_array(xData, mask=(xData==0))
                yDataMasked = np.ma.masked_array(yData, mask=(xData==0))
                segArtist.set_data(xDataMasked,yDataMasked)
                
            
        #update video frames 
        for vidNum, thisVidArtist in enumerate(vidAristList):
            vidCapObjList[vidNum].set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            success, image = vidCapObjList[vidNum].read()

            if success:
                thisVidArtist.set_array(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                vidCapObjList[vidNum].set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, image = vidCapObjList[vidNum].read()

            if useOpenPose:
                thisVidOpenPoseArtist_dict = list_of_vidOpenPoseArtistdicts[vidNum]
                update_2d_skel_segments(vidNum,'op_body')
                update_2d_skel_segments(vidNum,'op_rHand')
                update_2d_skel_segments(vidNum,'op_lHand')
                update_2d_skel_segments(vidNum,'op_face')
            
            if useMediaPipe:
                thisVidMediaPipeArtist_dict = list_of_vidMediaPipeArtistdicts[vidNum]
                update_2d_skel_segments(vidNum,'mp_body')
                update_2d_skel_segments(vidNum,'mp_rHand')
                update_2d_skel_segments(vidNum,'mp_lHand')

            if useDLC: #JSM NOTE - this one won't work, we'll need to fix it the next time we get DLC data
                thisVidDLCArtist[0].set_data(  dlcData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum,:,0], 
                                        dlcData_nCams_nFrames_nImgPts_XYC[vidNum,frameNum,:,1],)


        #shift timeseries xlims along with the frameNum
        xTimeSeriesAx.set_xlim([(frameNum/fps)-timeRange, (frameNum/fps)+timeRange])
        yTimeSeriesAx.set_xlim([(frameNum/fps)-timeRange, (frameNum/fps)+timeRange])
        for thisArtistKey in xCurrTimeArtists:

            xCurrTimeArtists[thisArtistKey][0].set_xdata(frameNum/fps) 
            yCurrTimeArtists[thisArtistKey][0].set_xdata(frameNum/fps) 
            if not thisArtistKey == 'blackLine':
                xCurrTimeArtists[thisArtistKey][0].set_ydata(xCurrTimeYdata[thisArtistKey][frameNum] ) 
                yCurrTimeArtists[thisArtistKey][0].set_ydata(yCurrTimeYdata[thisArtistKey][frameNum] ) 

        yCurrTimeArtists['frameNumber'].set_x(frameNum/fps+3/fps) 
        yCurrTimeArtists['frameNumber'].set_text('Frame# '+ str(frameNum))
        # if recordVid:
        #     thisFramePath = str(animationFramePath) + '/'+ str(session.sessionID) + "_frame_" + str(frameNum).zfill(6) + ".png"
        #     plt.savefig(thisFramePath)
        #     # fig.suptitle("nSessionID: {}, Frame: {} of {}".format(session.sessionID, frameNum, numFrames), fontsize=10)
        #     # animSlider.set_val(val=frameNum)

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
    ax3d.set_position([-.065, .28, .7, .7]) # [left, bottom, width, height])
    ax3d.set_xticklabels([])
    ax3d.set_yticklabels([])
    ax3d.set_zticklabels([])

    # ax3d.set_xlabel('X')
    # ax3d.set_ylabel('Y')
    # ax3d.set_zlabel('Z')
    # ax3d.set_axis_off()


    ax3d.tick_params(length=0) # WHY DOESNT THIS WORK? I HATE THOSE TICK MARKS >:(
    
    smoothData=True
    smoothWinLength = 5
    smoothOrder = 3

    if useOpenPose:
        try:
            openPose_skel_fr_mar_xyz = np.load(session.dataArrayPath / 'openPoseSkel_3d.npy')
            openPose_nCams_nFrames_nImgPts_XYC = np.load(session.dataArrayPath / 'openPoseData_2d.npy')
        except:
            print('No openPose data found.')

        if smoothData:
            for dim in range(openPose_skel_fr_mar_xyz.shape[2]):
                for mm in range(openPose_skel_fr_mar_xyz.shape[1]):
                    openPose_skel_fr_mar_xyz[:,mm,dim] = savgol_filter(openPose_skel_fr_mar_xyz[:,mm,dim], smoothWinLength, smoothOrder)

    if useMediaPipe:
        try:
            mediaPipe_skel_fr_mar_xyz = np.load(session.dataArrayPath / 'mediaPipeSkel_3d_smoothed.npy')
            mediaPipe_nCams_nFrames_nImgPts_XYC = np.load(session.dataArrayPath / 'mediaPipeData_2d.npy')            
        except:
            print('No mediaPipe data found.')
                
        if smoothData:
            for dim in range(mediaPipe_skel_fr_mar_xyz.shape[2]):
                for mm in range(mediaPipe_skel_fr_mar_xyz.shape[1]):
                    mediaPipe_skel_fr_mar_xyz[:,mm,dim] = savgol_filter(mediaPipe_skel_fr_mar_xyz[:,mm,dim], smoothWinLength, smoothOrder)

    try:
        charuco_fr_mar_xyz = np.load(session.dataArrayPath / 'charuco_3d_points.npy')
    except:
        console.warning('No charuco data found')

    


    figure_data = dict()
    if useOpenPose:
        figure_data['openPose_skel_trajectories|mar|fr_dim'] = [openPose_skel_fr_mar_xyz[:,markerNum,:] for markerNum in range(openPose_skel_fr_mar_xyz.shape[1])]
        figure_data['openPose_skel_fr_mar_xyz'] = openPose_skel_fr_mar_xyz

        dict_of_openPoseSegmentIdx_dicts, dict_of_op_skel_lineColor = formatOpenPoseStickIndices() #these will help us draw body and hands stick figures

    
    if useMediaPipe:
        mediaPipe_trajectories = [mediaPipe_skel_fr_mar_xyz[:,markerNum,:] for markerNum in range(mediaPipe_skel_fr_mar_xyz.shape[1])]
        figure_data['mediaPipe_skel_trajectories|mar|fr_dim'] = [mediaPipe_skel_fr_mar_xyz[:,markerNum,:] for markerNum in range(mediaPipe_skel_fr_mar_xyz.shape[1])]
        figure_data['mediaPipe_skel_fr_mar_xyz'] = mediaPipe_skel_fr_mar_xyz

        dict_of_mediaPipeSegmentIdx_dicts, dict_of_mp_skel_lineColor = formatMediaPipeStickIndices() #these will help us draw body and hands stick figures

    
    charuco_trajectories = [charuco_fr_mar_xyz[:,markerNum,:] for markerNum in range(charuco_fr_mar_xyz.shape[1])]
    figure_data['charuco_trajectories|mar|fr_dim'] = charuco_trajectories
    figure_data['charuco_fr_mar_xyz'] = charuco_fr_mar_xyz


    if useDLC:
        dlc_fr_mar_xyz = np.load(session.dataArrayPath / "deepLabCut_3d.npy")
        dlcData_nCams_nFrames_nImgPts_XYC = np.load(session.dataArrayPath / "deepLabCutData_2d.npy")
        
        for mm in range(dlc_fr_mar_xyz.shape[1]):
            for dim in range(dlc_fr_mar_xyz.shape[2]):
                dlc_fr_mar_xyz[:,mm,dim] = savgol_filter(dlc_fr_mar_xyz[:,mm,dim], 11, 3)

        ballTailLen = 6
        if ballTailLen > startFrame:
            startFrame = ballTailLen+1 #gotta do this, or the tail will index negative frames (without requiring annoying checks later)
    
        dlc_trajectories = [dlc_fr_mar_xyz[:,markerNum,:] for markerNum in range(dlc_fr_mar_xyz.shape[1])]    
        figure_data['dlc_trajectories|mar|fr_dim'] = dlc_trajectories
        figure_data['dlc_fr_mar_xyz'] = dlc_fr_mar_xyz

    
    
    
    def build_3d_segment_artist_dict(data_fr_mar_xyz,
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
                                                    data_fr_mar_xyz[startFrame, idxs ,0], 
                                                    data_fr_mar_xyz[startFrame, idxs ,1], 
                                                    data_fr_mar_xyz[startFrame, idxs ,2],
                                                    linestyle=lineStyle,
                                                    linewidth=lineWidth,
                                                    markerSize = marSize,
                                                    marker = markerType,
                                                    color = thisRGBA,
                                                    markeredgecolor = markerEdgeColor,
                                                    )[0]
        return dict_of_artist_objects

    

    matplotlib_artist_objs = dict()

    if useOpenPose:
        matplotlib_artist_objs['op_body'] = build_3d_segment_artist_dict(openPose_skel_fr_mar_xyz, dict_of_openPoseSegmentIdx_dicts['op_body'], segColor = dict_of_op_skel_lineColor)
        matplotlib_artist_objs['op_rHand'] = build_3d_segment_artist_dict(openPose_skel_fr_mar_xyz, dict_of_openPoseSegmentIdx_dicts['op_rHand'], segColor=np.append(humon_red, 1), markerType='.', markerEdgeColor = humon_red, lineWidth=1, marSize = 2)
        matplotlib_artist_objs['op_lHand'] = build_3d_segment_artist_dict(openPose_skel_fr_mar_xyz, dict_of_openPoseSegmentIdx_dicts['op_lHand'], segColor=np.append(humon_blue, 1), markerType='.', markerEdgeColor = humon_blue, lineWidth=1, marSize = 2)
        matplotlib_artist_objs['op_face'] = build_3d_segment_artist_dict(openPose_skel_fr_mar_xyz, dict_of_openPoseSegmentIdx_dicts['op_face'], segColor='k', lineWidth=.5)

    if useMediaPipe:
        matplotlib_artist_objs['mp_body'] = build_3d_segment_artist_dict(mediaPipe_skel_fr_mar_xyz, dict_of_mediaPipeSegmentIdx_dicts['mp_body'], segColor = dict_of_mp_skel_lineColor)
        matplotlib_artist_objs['mp_rHand'] = build_3d_segment_artist_dict(mediaPipe_skel_fr_mar_xyz, dict_of_mediaPipeSegmentIdx_dicts['mp_rHand'], segColor=np.append(humon_red, 1), markerType='.', markerEdgeColor = humon_red, lineWidth=1, marSize = 2)
        matplotlib_artist_objs['mp_lHand'] = build_3d_segment_artist_dict(mediaPipe_skel_fr_mar_xyz, dict_of_mediaPipeSegmentIdx_dicts['mp_lHand'], segColor=np.append(humon_blue, 1), markerType='.', markerEdgeColor = humon_blue, lineWidth=1, marSize = 2)

    if useDLC:
        dict_of_dlcSegmentIdx_dicts = dict()
        dict_of_dlcSegmentIdx_dicts['pinkBall'] = {'pinkBall': [0]}
        dict_of_dlcSegmentIdx_dicts['greenBall'] = {'greenBall': [1]}
        dict_of_dlcSegmentIdx_dicts['redBall'] = {'redBall': [2]}
        dict_of_dlcSegmentIdx_dicts['wobbleBoard'] = {'wobbleboard':[3,4,5,6,3,7,5,4,7,6]}
        dict_of_dlcSegmentIdx_dicts['wobbleWheel'] = {'wobbleWheel':[8,9]}
    
  
        ballColor = ['darkviolet', 'forestgreen', 'xkcd:goldenrod']
        matplotlib_artist_objs['pinkBall'] = build_3d_segment_artist_dict(dlc_fr_mar_xyz, dict_of_dlcSegmentIdx_dicts['pinkBall'], segColor=ballColor[0], markerType = 'o', marSize = 6, markerEdgeColor = 'indigo')
        matplotlib_artist_objs['redBall'] = build_3d_segment_artist_dict(dlc_fr_mar_xyz, dict_of_dlcSegmentIdx_dicts['redBall'], segColor=ballColor[2], markerType = 'o', marSize = 6, markerEdgeColor ='orangered')
        matplotlib_artist_objs['greenBall'] = build_3d_segment_artist_dict(dlc_fr_mar_xyz, dict_of_dlcSegmentIdx_dicts['greenBall'], segColor=ballColor[1], markerType = 'o', marSize = 6, markerEdgeColor ='darkgreen')

        matplotlib_artist_objs['wobbleBoard'] = build_3d_segment_artist_dict(dlc_fr_mar_xyz, dict_of_dlcSegmentIdx_dicts['wobbleBoard'], segColor='k', lineWidth=1)
        matplotlib_artist_objs['wobbleWheel'] = build_3d_segment_artist_dict(dlc_fr_mar_xyz, dict_of_dlcSegmentIdx_dicts['wobbleWheel'], segColor='k', lineWidth=1)

    if useOpenPose:
        op_skel_dottos = []
        for mm in range(67): #getcher dottos off my face!
            thisTraj = openPose_skel_fr_mar_xyz[:, mm, :]
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
            op_skel_dottos.append(thisDotto[0])

            matplotlib_artist_objs['op_skel_dottos'] = op_skel_dottos

    if useMediaPipe:
        matplotlib_artist_objs['mp_skel_dottos'] = [ax3d.plot(thisTraj[0, 0:1], thisTraj[1, 0:1], thisTraj[2, 0:1],'m.', markersize=1)[0] for thisTraj in mediaPipe_trajectories]

    matplotlib_artist_objs['charuco_dottos'] = [ax3d.plot(thisTraj[0, 0:1], thisTraj[1, 0:1], thisTraj[2, 0:1],'m.', markersize=1)[0] for thisTraj in charuco_trajectories]

    
    if useDLC:
        matplotlib_artist_objs['dlc_dottos'] = [ax3d.plot(thisTraj[0, 0:1], thisTraj[1, 0:1], thisTraj[2, 0:1],'b.', markersize=1)[0] for thisTraj in dlc_trajectories]

        matplotlib_artist_objs['ball_tails'] = [ax3d.plot( 
                                                dlc_trajectories[bb][startFrame-ballTailLen:startFrame, 0],
                                                dlc_trajectories[bb][startFrame-ballTailLen:startFrame, 1],
                                                dlc_trajectories[bb][startFrame-ballTailLen:startFrame, 2],
                                                '-', color=ballColor[bb])[0] for bb in range(3)]
    

    if useOpenPose:
        numFrames = openPose_skel_fr_mar_xyz.shape[0]
        mx = np.nanmean(openPose_skel_fr_mar_xyz[int(numFrames/2),:,0])
        my = np.nanmean(openPose_skel_fr_mar_xyz[int(numFrames/2),:,1])
        mz = np.nanmean(openPose_skel_fr_mar_xyz[int(numFrames/2),:,2])

    if useMediaPipe:
        numFrames = mediaPipe_skel_fr_mar_xyz.shape[0]
        mx = np.nanmean(mediaPipe_skel_fr_mar_xyz[int(numFrames/2),:,0])
        my = np.nanmean(mediaPipe_skel_fr_mar_xyz[int(numFrames/2),:,1])
        mz = np.nanmean(mediaPipe_skel_fr_mar_xyz[int(numFrames/2),:,2])

    
    if np.isnan(mx) or np.isnan(my) or np.isnan(mz):
        mx = 0
        my = 0
        mz = 0
    # groundX = np.arange(mx-100,mx+100)
    # groundZ = np.arange(my-100,my+100)
    # groundXX, groundZZ = np.meshgrid(groundX, groundZ)
    # groundYY = np.zeros_like(groundXX)
    # groundMesh = ax3d.plot_surface(groundXX, groundZZ, groundYY, color='k', alpha=.5)

    axRange = 1000#session.board.square_length * 10

    # Setting the axes properties
    ax3d.set_xlim3d([mx-axRange, mx+axRange])
    ax3d.set_ylim3d([my-axRange, my+axRange])
    ax3d.set_zlim3d([mz-axRange, mz+axRange])
    
    tit1 = fig.text(.5, .96, "The FreeMoCap Project", fontsize=15, horizontalalignment='center')
    tit2 = fig.text(.5, .92, "Session: {}".format(session.sessionID), fontsize=8, horizontalalignment='center')



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
    numVids = len(syncedVidPathListAll)

    syncedVidPathList  = syncedVidPathListAll.copy()

    vidAxesList = []
    vidAristList = []
    vidCapObjList = []

    list_of_vidOpenPoseArtistdicts = []
    list_of_vidMediaPipeArtistdicts = []
    
    if useDLC: vidDLCArtistList = []    

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

    # vidImageGrid = ImageGrid(fig, [.45, 0.05, .54, .9], nrows_ncols = (2,2), axes_pad = 0.1) # https://matplotlib.org/stable/gallery/axes_grid1/simple_axesgrid.html
    if numVids < 4:
        numRows = numVids
        numCols = 1
    else:
        numRows = int(np.ceil(numVids/2))
        numCols = 2


    vidAxGridSpec = fig.add_gridspec(numRows, numCols, left=.55, bottom=.025, right=.9, top=.9, wspace=.1, hspace=.1)


    for thisVidNum, thisVidPath in enumerate(syncedVidPathList):
        #make subplot for figure (and set position)

        if numVids < 4:
            thisVidAxis = fig.add_subplot(vidAxGridSpec[thisVidNum])
        elif numVids %2 > 0: #if odd number videos plot the first vid across 2 spots
            if thisVidNum==0:
                thisVidAxis = fig.add_subplot(vidAxGridSpec[0,:])
            else:
                thisVidAxis = fig.add_subplot(vidAxGridSpec[thisVidNum+1])
        else: 
            thisVidAxis = fig.add_subplot(vidAxGridSpec[thisVidNum])


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
            vidOpenPoseArtist_dict['op_body'] = build_2d_segment_artist_dict(thisVidNum, openPose_nCams_nFrames_nImgPts_XYC, dict_of_openPoseSegmentIdx_dicts['op_body'], segColor = dict_of_op_skel_lineColor)
            vidOpenPoseArtist_dict['op_rHand'] = build_2d_segment_artist_dict(thisVidNum, openPose_nCams_nFrames_nImgPts_XYC, dict_of_openPoseSegmentIdx_dicts['op_rHand'], segColor=np.append(humon_red, .75), lineWidth=.5)
            vidOpenPoseArtist_dict['op_lHand'] = build_2d_segment_artist_dict(thisVidNum, openPose_nCams_nFrames_nImgPts_XYC, dict_of_openPoseSegmentIdx_dicts['op_lHand'], segColor=np.append(humon_blue, .75), lineWidth=.5)
            vidOpenPoseArtist_dict['op_face'] = build_2d_segment_artist_dict(thisVidNum, openPose_nCams_nFrames_nImgPts_XYC, dict_of_openPoseSegmentIdx_dicts['op_face'], segColor = np.array([1.,1.,1.,1]), lineWidth=.25)
            list_of_vidOpenPoseArtistdicts.append(vidOpenPoseArtist_dict)

        if useMediaPipe:
            vidMediaPipeArtist_dict = dict()            
            vidMediaPipeArtist_dict['mp_body'] = build_2d_segment_artist_dict(thisVidNum, mediaPipe_nCams_nFrames_nImgPts_XYC, dict_of_mediaPipeSegmentIdx_dicts['mp_body'], segColor = 'g')
            vidMediaPipeArtist_dict['mp_rHand'] = build_2d_segment_artist_dict(thisVidNum, mediaPipe_nCams_nFrames_nImgPts_XYC, dict_of_mediaPipeSegmentIdx_dicts['mp_rHand'], segColor=np.append(humon_red, .75), lineWidth=.5)
            vidMediaPipeArtist_dict['mp_lHand'] = build_2d_segment_artist_dict(thisVidNum, mediaPipe_nCams_nFrames_nImgPts_XYC, dict_of_mediaPipeSegmentIdx_dicts['mp_lHand'], segColor=np.append(humon_blue, .75), lineWidth=.5)
            list_of_vidMediaPipeArtistdicts.append(vidMediaPipeArtist_dict)


        if useDLC:
            
            vidDLCArtistList.append(thisVidAxis.plot(
                                    dlcData_nCams_nFrames_nImgPts_XYC[thisVidNum,startFrame,:,0], 
                                    dlcData_nCams_nFrames_nImgPts_XYC[thisVidNum,startFrame,:,1],
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
    timestamps = np.arange(0, numFrames)/fps
    if useMediaPipe:
        rHandIdx = 20
        lHandIdx = 19
        rHandX = mediaPipe_skel_fr_mar_xyz[:,rHandIdx,0]/1000 #convert mm to meters
        rHandY = -mediaPipe_skel_fr_mar_xyz[:,rHandIdx,1]/1000
        lHandX = mediaPipe_skel_fr_mar_xyz[:,lHandIdx,0]/1000
        lHandY = -mediaPipe_skel_fr_mar_xyz[:,lHandIdx,1]/1000

    if useOpenPose:
        rHandIdx = 4
        lHandIdx = 7
        rHandX = openPose_skel_fr_mar_xyz[:,rHandIdx,0]/1000 #convert mm to meters
        rHandY = -openPose_skel_fr_mar_xyz[:,rHandIdx,1]/1000
        lHandX = openPose_skel_fr_mar_xyz[:,lHandIdx,0]/1000
        lHandY = -openPose_skel_fr_mar_xyz[:,lHandIdx,1]/1000

    
    linePlotWidth = .45
    linePlotHeight = .14

    yTimeSeriesAx = fig.add_subplot(position=[.07, .225, linePlotWidth, linePlotHeight])
    yTimeSeriesAx.set_title('Hand Position vs Time', fontsize = 7, pad=2)

    yTimeSeriesAx.plot(timestamps, rHandY, color=humon_red, linewidth=.75, label='Right Hand')
    yTimeSeriesAx.plot(timestamps, lHandY, color=humon_blue, linewidth=.75, label='Left Hand')
    
    timeRange = 3
    ylimRange = .6

    yCurrTimeArtists = dict()
    yCurrTimeYdata = dict()
    yCurrTimeArtists['blackLine']  = yTimeSeriesAx.plot([startFrame/fps, startFrame/fps], [-ylimRange, ylimRange*2], color='k', linewidth=1)

    yCurrTimeArtists['rHandDot']  = yTimeSeriesAx.plot([startFrame/fps], [rHandY[startFrame]], markeredgecolor=humon_red, markerfacecolor = 'k',marker='o', markersize=3)
    yCurrTimeYdata['rHandDot'] = rHandY
    yCurrTimeArtists['lHandDot']  = yTimeSeriesAx.plot([startFrame/fps], [lHandY[startFrame]], markeredgecolor=humon_blue, markerfacecolor = 'k', marker='o', markersize=3)
    yCurrTimeYdata['lHandDot'] = lHandY
    
    
    yCurrTimeArtists['frameNumber'] = yTimeSeriesAx.text(startFrame/fps+3/fps, ylimRange*.7, "Frame# " + str(startFrame), fontsize=6)

    yTimeSeriesAx.tick_params(labelsize=6, direction='in', width=.5)
    yTimeSeriesAx.tick_params( pad=2)
    

    yTimeSeriesAx.set_ylabel('Vertical (m)', fontsize=7, labelpad=3)
    yTimeSeriesAx.set_ylim([-ylimRange, ylimRange])
    yTimeSeriesAx.set_xlim([(startFrame/fps)-timeRange, (startFrame/fps)+timeRange])

    

    for axis in ['top','bottom','left','right']:
        yTimeSeriesAx.spines[axis].set_linewidth(0.5)



    yTimeSeriesAx.legend(loc='upper left', fontsize=6)



    xTimeSeriesAx = fig.add_subplot(position=[.07, 0.05, linePlotWidth, linePlotHeight])
    
    xTimeSeriesAx.plot(timestamps, rHandX, color=humon_red, linewidth=.75, label='Right Hand')
    xTimeSeriesAx.plot(timestamps, lHandX, color=humon_blue, linewidth=.75, label='Left Hand')
    


    xCurrTimeArtists = dict()
    xCurrTimeYdata = dict()
    xCurrTimeArtists['blackLine']  = xTimeSeriesAx.plot([startFrame/fps, startFrame/fps], [-ylimRange, ylimRange], color='k', linewidth=1)
    xCurrTimeArtists['rHandDot']  = xTimeSeriesAx.plot([startFrame/fps], [rHandX[startFrame]], markeredgecolor=humon_red, markerfacecolor = 'k',marker='o', markersize=3)
    xCurrTimeYdata['rHandDot'] = rHandX
    xCurrTimeArtists['lHandDot']  = xTimeSeriesAx.plot([startFrame/fps], [lHandX[startFrame]], markeredgecolor=humon_blue, markerfacecolor = 'k', marker='o', markersize=3)
    xCurrTimeYdata['lHandDot'] = lHandX



    xTimeSeriesAx.tick_params(labelsize=6, direction='in', width=.5)
    xTimeSeriesAx.tick_params( pad=2)
    
    xTimeSeriesAx.set_ylabel('Left/Right (m)', fontsize=7, labelpad=0)
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

    # thisVidAxis.text(-565,1440, 'Music - artist: Neon Exdeath, song: Meowmaline, album: Jewel Tones',color=humon_green, fontsize=6)
    thisVidAxis.text(0,thisVidCap.get(cv2.CAP_PROP_FRAME_HEIGHT)*1.06, 'github.com/jonmatthis/freemocap || freemocap.org',color=humon_green, fontsize=6)

    logoAx = fig.add_subplot(position=[.85, .85, .15, .15])
    # logoIm = cv2.imread(r'logo\fmc-logo-black-border-white-bkgd.png') #JSM NOTE - THis doesn't work, but SOMETIMES IT DOES?!
    # if logoIm is not None:  logoAx.imshow(cv2.cvtColor(logoIm, cv2.COLOR_BGR2RGB))
    logoAx.axis('off')
    
    # if recordVid:
    #     animationFramePath = session.sessionPath / "animationFrames"
    #     animationFramePath.mkdir(parents=True, exist_ok=True)

    # Creating the Animation object
    out_animation = animation.FuncAnimation(fig, update_figure, range(startFrame,numFrames), fargs=(),
                                    interval=1, blit=False)


    
    if recordVid:
        # vidSavePath = '{}_animVid.mp4'.format(str(session.sessionPath / session.sessionID))
        gifSavePath = '{}_animVid.gif'.format(str(session.sessionPath / session.sessionID)) #NOTE - saving as a gif first then converting to MP4, because saving directly to MP4 requires users to install ffmpeg (independently of the pip install)
        with console.status('Saving animation for {}'.format(session.sessionID)):

            # ffmpeg, not actually much faster :-/            
            # tik = time.time()            
            # vidSavePath = f'{str(session.sessionPath / session.sessionID)}_outVid.mp4'
            # video_writer = animation.FFMpegWriter(fps=fps)
            # out_animation.save(vidSavePath, writer=video_writer)
            # print(f'Done! Saved animation video to: {str(vidSavePath)}')
            # tok = time.time()-tik
            # print(f'Took {tok} seconds to save animation video wtih ffmpeg')
            # # # except:
                
            tik = time.time()            
            Writer = animation.writers['pillow']            
            writer = Writer(fps=fps, metadata=dict(artist='FreeMoCap'))#, bitrate=1800)
            out_animation.save(gifSavePath, writer = writer)
            gif_filepath = mp.VideoFileClip(gifSavePath)
            gif_filepath.write_videofile(gifSavePath.replace('.gif','.mp4'))
            os.remove(gifSavePath)
            tok = time.time()-tik
            print(f'Took {tok} seconds to save animation video wtih pillow')




    try:
        if showAnimation:
            with console.status('Playing Skeleton animation! Close the `matplotlib` window to continue...'):
                plt.pause(0.1)
                plt.draw()
    except:
        pass



  


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
    openPoseHandIds = a dictionary of arrays containing indices of individual hand segments, along with offset to know where to start in the 'skel_fr_mar_xyz.shape[1]' part of the array
    dict_of_op_skel_lineColor = a dictionary of arrays, each containing the color (RGBA) to use for a given body segment
    """
    dict_of_openPoseSegmentIdx_dicts = dict()

    #make body dictionary
    openPoseBodySegmentIds = dict()
    openPoseBodySegmentIds['op_head'] = [17, 15, 0, 1,0, 16, 18, ]
    openPoseBodySegmentIds['op_spine'] = [1,8,5,1, 2, 12, 8, 9, 5, 1, 2, 8]
    openPoseBodySegmentIds['op_rArm'] = [1, 2, 3, 4, ]
    openPoseBodySegmentIds['op_lArm'] = [1, 5, 6, 7, ]
    openPoseBodySegmentIds['op_rLeg'] = [8, 9, 10, 11, 22, 23, 11, 24, ]
    openPoseBodySegmentIds['op_lLeg'] = [8,12, 13, 14, 19, 20, 14, 21,]
    dict_of_openPoseSegmentIdx_dicts['op_body'] = openPoseBodySegmentIds


    #make colors dictionary
    openPoseBodyColor = np.array([50, 89, 0])/255
    openPoseRightColor = np.array([230, 50, 0])/255
    openPoseLeftColor = np.array([0, 50, 230])/255
    
    dict_of_op_skel_lineColor = dict()
    dict_of_op_skel_lineColor['op_head'] = np.append(openPoseBodyColor, 0.5)
    dict_of_op_skel_lineColor['op_spine'] = np.append(openPoseBodyColor, 1)
    dict_of_op_skel_lineColor['op_rArm'] = np.append(openPoseRightColor, 1)
    dict_of_op_skel_lineColor['op_lArm'] = np.append(openPoseLeftColor, 1)
    dict_of_op_skel_lineColor['op_rLeg'] = np.append(openPoseRightColor, 1)
    dict_of_op_skel_lineColor['op_lLeg'] = np.append(openPoseLeftColor, 1)


    # Make some handy maps ;D
    openPoseHandIds = dict()
    rHandIDstart = 25
    lHandIDstart = rHandIDstart + 21

    openPoseHandIds['op_thumb'] = np.array([0, 1, 2, 3, 4,  ]) 
    openPoseHandIds['op_index'] = np.array([0, 5, 6, 7, 8, ])
    openPoseHandIds['op_bird']= np.array([0, 9, 10, 11, 12, ])
    openPoseHandIds['op_ring']= np.array([0, 13, 14, 15, 16, ])
    openPoseHandIds['op_pinky'] = np.array([0, 17, 18, 19, 20, ])
    

    rHand_dict = copy.deepcopy(openPoseHandIds.copy()) #copy.deepcopy() is necessary to make sure the dicts are independent of each other
    lHand_dict = copy.deepcopy(rHand_dict)

    for key in rHand_dict: 
        rHand_dict[key] += rHandIDstart 
        lHand_dict[key] += lHandIDstart 

    dict_of_openPoseSegmentIdx_dicts['op_rHand'] = rHand_dict
    dict_of_openPoseSegmentIdx_dicts['op_lHand'] = lHand_dict

    
    #how to face --> :D <--
    openPoseFaceIDs = dict()
    faceIDStart = 67
    #define face parts
    openPoseFaceIDs['op_jaw'] = np.arange(0,16) + faceIDStart 
    openPoseFaceIDs['op_rBrow'] = np.arange(17,21) + faceIDStart
    openPoseFaceIDs['op_lBrow'] = np.arange(22,26) + faceIDStart
    openPoseFaceIDs['op_noseRidge'] = np.arange(27,30) + faceIDStart
    openPoseFaceIDs['op_noseBot'] = np.arange(31,35) + faceIDStart
    openPoseFaceIDs['op_rEye'] = np.concatenate((np.arange(36,41), [36])) + faceIDStart
    openPoseFaceIDs['op_lEye'] = np.concatenate((np.arange(42,47), [42])) + faceIDStart    
    openPoseFaceIDs['op_upperLip'] = np.concatenate((np.arange(48,54), np.flip(np.arange(60, 64)), [48])) + faceIDStart
    openPoseFaceIDs['op_lowerLip'] = np.concatenate(([60], np.arange(64,67), np.arange(54, 59), [48], [60])) + faceIDStart
    openPoseFaceIDs['op_rPupil'] = np.array([68]) + faceIDStart
    openPoseFaceIDs['op_lPupil'] = np.array([69]) + faceIDStart #nice

    dict_of_openPoseSegmentIdx_dicts['op_face'] = openPoseFaceIDs
    
    return dict_of_openPoseSegmentIdx_dicts, dict_of_op_skel_lineColor



###  
###  ███████  ██████  ██████  ███    ███  █████  ████████     ███    ███ ███████ ██████  ██  █████  ██████  ██ ██████  ███████     ███████ ██   ██ ███████ ██      
###  ██      ██    ██ ██   ██ ████  ████ ██   ██    ██        ████  ████ ██      ██   ██ ██ ██   ██ ██   ██ ██ ██   ██ ██          ██      ██  ██  ██      ██      
###  █████   ██    ██ ██████  ██ ████ ██ ███████    ██        ██ ████ ██ █████   ██   ██ ██ ███████ ██████  ██ ██████  █████       ███████ █████   █████   ██      
###  ██      ██    ██ ██   ██ ██  ██  ██ ██   ██    ██        ██  ██  ██ ██      ██   ██ ██ ██   ██ ██      ██ ██      ██               ██ ██  ██  ██      ██      
###  ██       ██████  ██   ██ ██      ██ ██   ██    ██        ██      ██ ███████ ██████  ██ ██   ██ ██      ██ ██      ███████     ███████ ██   ██ ███████ ███████ 
###                                                                                                                                                                
###                                                                                                                                                                                                                                                                                                                                       
def formatMediaPipeStickIndices():
    """
    generate dictionary of arrays, each containing the 'connect-the-dots' order to draw a given body segment
    
    returns:
    mediaPipeBodySegmentIds= a dictionary of arrays containing indices of individual body segments (Note, a lot of markerless mocap comp sci types like to say 'pose' instead of 'body'. They also use 'pose' to refer to camera 6 DoF position sometimes. Comp sci is frustrating like that lol)
    mediaPipeHandIds = a dictionary of arrays containing indices of individual hand segments, along with offset to know where to start in the 'skel_fr_mar_xyz.shape[1]' part of the array
    dict_of_mp_skel_lineColor = a dictionary of arrays, each containing the color (RGBA) to use for a given body segment
    """
    dict_of_mediaPipeSegmentIdx_dicts = dict()

    #make body dictionary
    mediaPipeBodySegmentIds = dict()
    mediaPipeBodySegmentIds['mp_head'] = [8, 6, 5, 4, 0, 10, 9, 0, 1, 2, 3, 7 ]
    mediaPipeBodySegmentIds['mp_tors'] = [12, 11, 24, 23, 12]
    mediaPipeBodySegmentIds['mp_rArm'] = [12, 14, 16, 18, 20, 16, 22 ]
    mediaPipeBodySegmentIds['mp_lArm'] = [11, 13, 15, 17, 19, 15, 21]
    mediaPipeBodySegmentIds['mp_rLeg'] = [24, 26, 28, 30, 32, 28, ]
    mediaPipeBodySegmentIds['mp_lLeg'] = [23, 25, 27, 29, 31, 27, ]
    dict_of_mediaPipeSegmentIdx_dicts['mp_body'] = mediaPipeBodySegmentIds

    #make colors dictionary
    mediaPipeBodyColor = np.array([125,106,0])/255
    mediaPipeRightColor = np.array([230, 0, 169])/255
    mediaPipeLeftColor = np.array([0, 176, 176])/255
    dict_of_mp_skel_lineColor = dict()
    
    dict_of_mp_skel_lineColor['mp_head'] = np.append(mediaPipeBodyColor, .5)
    dict_of_mp_skel_lineColor['mp_tors'] = np.append(mediaPipeBodyColor, 1)
    dict_of_mp_skel_lineColor['mp_rArm'] = np.append(mediaPipeRightColor, 1)
    dict_of_mp_skel_lineColor['mp_lArm'] = np.append(mediaPipeLeftColor, 1)
    dict_of_mp_skel_lineColor['mp_rLeg'] = np.append(mediaPipeRightColor, 1)
    dict_of_mp_skel_lineColor['mp_lLeg'] = np.append(mediaPipeLeftColor, 1)


    # Make some handy maps ;D
    mediaPipeHandIds = dict()
    rHandIDstart = 33
    lHandIDstart = rHandIDstart + 21

    mediaPipeHandIds['mp_thumb'] = np.array([0, 1, 2, 3, 4,  ]) 
    mediaPipeHandIds['mp_index'] = np.array([0, 5, 6, 7, 8, ])
    mediaPipeHandIds['mp_bird']= np.array([0, 9, 10, 11, 12, ])
    mediaPipeHandIds['mp_ring']= np.array([0, 13, 14, 15, 16, ])
    mediaPipeHandIds['mp_pinky'] = np.array([0, 17, 18, 19, 20, ])
    

    rHand_dict = copy.deepcopy(mediaPipeHandIds.copy()) #copy.deepcopy() is necessary to make sure the dicts are independent of each other
    lHand_dict = copy.deepcopy(rHand_dict)

    for key in rHand_dict: 
        rHand_dict[key] += rHandIDstart 
        lHand_dict[key] += lHandIDstart 

    dict_of_mediaPipeSegmentIdx_dicts['mp_rHand'] = rHand_dict
    dict_of_mediaPipeSegmentIdx_dicts['mp_lHand'] = lHand_dict

    
    # #how to face --> :D <--
    # mediaPipeFaceIDs = dict()
    # faceIDStart = 67
    # #define face parts
    # mediaPipeFaceIDs['mp_jaw'] = np.arange(0,16) + faceIDStart 
    # mediaPipeFaceIDs['mp_rBrow'] = np.arange(17,21) + faceIDStart
    # mediaPipeFaceIDs['mp_lBrow'] = np.arange(22,26) + faceIDStart
    # mediaPipeFaceIDs['mp_noseRidge'] = np.arange(27,30) + faceIDStart
    # mediaPipeFaceIDs['mp_noseBot'] = np.arange(31,35) + faceIDStart
    # mediaPipeFaceIDs['mp_rEye'] = np.concatenate((np.arange(36,41), [36])) + faceIDStart
    # mediaPipeFaceIDs['mp_lEye'] = np.concatenate((np.arange(42,47), [42])) + faceIDStart    
    # mediaPipeFaceIDs['mp_upperLip'] = np.concatenate((np.arange(48,54), np.flip(np.arange(60, 64)), [48])) + faceIDStart
    # mediaPipeFaceIDs['mp_lowerLip'] = np.concatenate(([60], np.arange(64,67), np.arange(54, 59), [48], [60])) + faceIDStart
    # mediaPipeFaceIDs['mp_rPupil'] = np.array([68]) + faceIDStart
    # mediaPipeFaceIDs['mp_lPupil'] = np.array([69]) + faceIDStart #nice

    # dict_of_mediaPipeSegmentIdx_dicts['mp_face'] = mediaPipeFaceIDs
    
    return dict_of_mediaPipeSegmentIdx_dicts, dict_of_mp_skel_lineColor


if __name__ == '__main__':
    PlaySkeletonAnimation()
