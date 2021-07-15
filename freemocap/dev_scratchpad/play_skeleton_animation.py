
"""
============
3D animation
============

An animated plot in 3D.
from - https://matplotlib.org/2.1.2/gallery/animation/simple_3danim.html
"""
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



def PlaySkeletonAnimation(
    session=None,
    vidType=1,
    startFrame=40,
    azimuth=-90,
    elevation=-80,
    useOpenPose=True,
    useMediaPipe=False,
    useDLC=False,
    ):
  
    def update_figure(frameNum):
        """ 
        Called by matplotlib animator for each frame.
        """
        
        skel_dottos = matplotlib_artist_objs['skel_dottos'] 
        skel_trajectories = figure_data['skel_trajectories|mar|fr_dim']


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
        marNum = -1
        for thisSkelDotto, thisTraj in zip(skel_dottos,skel_trajectories):
            marNum+=1
            # NOTE: there is no .set_data() for 3 dim data...
            thisSkelDotto.set_data(thisTraj[ frameNum-1, 0:2])
            thisSkelDotto.set_3d_properties(thisTraj[ frameNum-1, 2])

        for vidNum, thisVidArtist in enumerate(vidAristList):
            success, image = vidCapObjList[vidNum].read()
            thisVidArtist.set_array(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


        # animSlider.set_val(val=frameNum)

    ##
    ##
    ## Create the figure for the plot
    ##
    ##

    fig = plt.figure(dpi=150)
    plt.ion()

    ###
    ###
    ### Attaching 3D axis to the figure
    ###
    ###
    
    ax3d = p3.Axes3D(fig)
    ax3d.set_position([.1, .1, .8, .8]) # [left, bottom, width, height])



    skel_fr_mar_dim = np.load(r"C:\Users\jonma\Dropbox\GitKrakenRepos\freemocap\Data\sesh_21-07-08_131030\DataArrays\openPoseSkel_3d.npy")
    skel_trajectories = [skel_fr_mar_dim[:,markerNum,:] for markerNum in range(skel_fr_mar_dim.shape[1])]
    
    figure_data = dict()
    figure_data['skel_trajectories|mar|fr_dim'] = skel_trajectories
    figure_data['skel_fr_mar_dim'] = skel_fr_mar_dim




    dict_of_openPoseSegmentIdx_dicts = formatOpenPoseStickIndices() #these will help us draw body and hands stick figures
    
    def build_segment_artist_dict(dict_of_list_of_segment_idxs):       
        """ 
        Builds a dictionary of line artists for each body segment.
        """       
        segNames = list(dict_of_list_of_segment_idxs)

        dict_of_artist_objects = dict()
        for segName in segNames:
            dict_of_artist_objects[segName]  = ax3d.plot(
                                                    skel_fr_mar_dim[0,dict_of_list_of_segment_idxs[segName],0], 
                                                    skel_fr_mar_dim[0,dict_of_list_of_segment_idxs[segName],1], 
                                                    skel_fr_mar_dim[0,dict_of_list_of_segment_idxs[segName],2],
                                                    'k-'
                                                    )[0]
        return dict_of_artist_objects

    

    matplotlib_artist_objs = dict()
    matplotlib_artist_objs['body'] = build_segment_artist_dict(dict_of_openPoseSegmentIdx_dicts['body'])
    matplotlib_artist_objs['rHand'] = build_segment_artist_dict(dict_of_openPoseSegmentIdx_dicts['rHand'])
    matplotlib_artist_objs['lHand'] = build_segment_artist_dict(dict_of_openPoseSegmentIdx_dicts['lHand'])
    matplotlib_artist_objs['face'] = build_segment_artist_dict(dict_of_openPoseSegmentIdx_dicts['face'])

    matplotlib_artist_objs['skel_dottos'] = [ax3d.plot(thisTraj[0, 0:1], thisTraj[1, 0:1], thisTraj[2, 0:1],'r,')[0] for thisTraj in skel_trajectories]
    numFrames = skel_fr_mar_dim.shape[0]
   



    mx = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,0])
    my = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,1])
    mz = np.nanmean(skel_fr_mar_dim[int(numFrames/2),:,2])

    axRange = 800#session.board.square_length * 10

    # Setting the axes properties
    ax3d.set_xlim3d([mx-axRange, mx+axRange])
    ax3d.set_xlabel('X')

    ax3d.set_ylim3d([my-axRange, my+axRange])
    ax3d.set_ylabel('Y')

    ax3d.set_zlim3d([mz-axRange, mz+axRange])
    ax3d.set_zlabel('Z')

    ax3d.set_title('3D Test')

    ax3d.view_init(azim=azimuth, elev=elevation)
    




    ###
    ###
    ### Make Video Image subplots
    ###
    ###
    syncedVidPath = Path(r'C:\Users\jonma\Dropbox\GitKrakenRepos\freemocap\Data\sesh_21-07-08_131030\SyncedVideos')
    
    syncedVidPathList = list(sorted(syncedVidPath.glob('*.mp4')))
    
    #remove a few vids, 6 is too many!
    syncedVidPathList.pop(5) 
    syncedVidPathList.pop(1)
    
    vidAxesList = []
    vidAristList = []
    vidCapObjList = []
    
    vidAx_positions = []
    vidAx_positions.append([ .5, .5, .25, .25])
    vidAx_positions.append([.75, .5, .25, .25])
    vidAx_positions.append([ .5, .0, .25, .25])
    vidAx_positions.append([.75, .0, .25, .25])

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

        #create artist object for each video NOTE - will need to sych this with start frame somehow
        success, image  = vidCapObjList[-1].read()
        assert success==True, "{} - failed to load an image".format(thisVidPath.stem) #make sure we have a frame
        vidAristList.append(plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))

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
    line_animation = animation.FuncAnimation(fig, update_figure, range(200,numFrames), fargs=(),
                                    interval=1, blit=False)


    plt.pause(0.1)
    plt.draw()

    with console.status('saving video...'):
        Writer = animation.writers['ffmpeg']
        writer = Writer(fps=30, metadata=dict(artist='FreeMoCap'), bitrate=1800)
        line_animation.save('out.mp4', writer = writer)
    

    
    console.print(":sparkle: :skull: :sparkle:")


def formatOpenPoseStickIndices():
    """
    generate dictionary of arrays, each containing the 'connect-the-dots' order to draw a given body segment
    
    returns:
     openPoseBodySegmentIds= a dictionary of arrays containing indices of individual body segments (Note, a lot of markerless mocap comp sci types like to say 'pose' instead of 'body'. They also use 'pose' to refer to camera 6 DoF position sometimes. Comp sci is frustrating like that lol)
     openPoseHandIds = a dictionary of arrays containing indices of individual hand segments, along with offset to know where to start in the 'skel_fr_mar_dim.shape[1]' part of the array
    """
    dict_of_openPoseSegmentIdx_dicts = dict()

    #make body dictionary
    openPoseBodySegmentIds = dict()
    openPoseBodySegmentIds['head'] = [17, 15, 0, 16, 18, ]
    openPoseBodySegmentIds['spine'] = [0,1,8,5,1, 2, 12, 8, 9, 5, 1, 2, 8]
    openPoseBodySegmentIds['rArm'] = [1, 2, 3, 4, ]
    openPoseBodySegmentIds['lArm'] = [1, 5, 6, 7, ]
    openPoseBodySegmentIds['rLeg'] = [8, 9, 10, 11, 22, 23, 11, 24, ]
    openPoseBodySegmentIds['lLeg'] = [8,12, 13, 14, 19, 20, 14, 21,]
    dict_of_openPoseSegmentIdx_dicts['body'] = openPoseBodySegmentIds

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
    
    return dict_of_openPoseSegmentIdx_dicts



if __name__ == '__main__':
    PlaySkeletonAnimation()
