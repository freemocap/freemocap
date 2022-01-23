
# %%
import concurrent.futures
import logging
import queue
import random
import threading
import time
import platform

import cv2
import matplotlib.pyplot as plt
import numpy as np
import h5py
from pathlib import Path

from rich import print
from rich import inspect

def CamRecordThread(camCap, webcam_frames_queue, barrier, exit_event, camNum):
    """Pretend we're getting a number from the network."""
    while not exit_event.is_set():
        
        try:
            success, frame_image = camCap.read()
            timestamp = time.time()
            cam_num_tuple = (camNum, )
            frame_timestamp_tuple = (frame_image, timestamp)
            cam_frame_timestamp_tuple = cam_num_tuple+frame_timestamp_tuple
            webcam_frames_queue.put(cam_frame_timestamp_tuple)
            log_msg = 'Camera '+ str(camNum)+" got a frame at timestamp:"+ str(timestamp) + ' queue size: ' + str(webcam_frames_queue.qsize())
            print(log_msg)
            logging.info(log_msg)
            barrier.wait()

        except Exception as ex:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            logging.info(message)
            print(message)
            exit_event.set()


    camCap.release()
    logging.info("Producer received exit_event. Exiting")

# def incoming_frames_handler(webcam_frames_queue, exit_event):
#     """Pretend we're saving a number in the database."""
#     while not exit_event.is_set() or not webcam_frames_queue.empty():
#         try: 
#             cam_frame_timestamp_tuple= webcam_frames_queue.get() #tuple(camNum, (frame_image,timestamp))

#             camID = cam_frame_timestamp_tuple[0]
#             frame_timestamp_tuple = cam_frame_timestamp_tuple[1]
#             thisFrame = frame_timestamp_tuple[0]
#             thisTimestamp = frame_timestamp_tuple[1]

#             allTimestamps.append(thisTimestamp)
#             camTimestamps_list[camID] = np.append(camTimestamps_list[camID], thisTimestamp)

#             logging.info(
#                 "IncomingFrameHandler got the frame from camera#"+str(camID)+" with timestamp: %s (size=%d)", str(thisTimestamp), webcam_frames_queue.qsize()
#             )
            


#         except:
#             print('something broke in the incoming_frame_handler')
#             exit_event.set()

#     logging.info("Consumer received exit_event . Exiting")

def saveMultiViewToMP4():
    multiIm = None
    theseFrames_list = [None]* numCams #create an empty list with numCams entries (Python is weird sometimes, lol)
    theseFrameTuples_list = theseFrames_list
    theseTimestamps = np.empty(numCams)
    
    while webcam_frames_queue.qsize() > 0:
        this_cam_frame_timestamp_tuple = webcam_frames_queue.get() #(camNum,(frame,timestamp))        
        camNum = this_cam_frame_timestamp_tuple[0]
        theseFrames_list[camNum] = this_cam_frame_timestamp_tuple[1]
        thisTimestamp = this_cam_frame_timestamp_tuple[2]
        theseTimestamps[camNum] = thisTimestamp
        camTimestamps_list[camNum] = np.append(camTimestamps_list[camNum], thisTimestamp)

    # allMultiframes.append(theseFrameTuples_list)

    for camNum, image in enumerate(theseFrames_list):
        if camNum==0:
            multiIm = image
        else:
            multiIm = cv2.hconcat([multiIm, image])

    multiFrame_queue.put(multiIm)
    print('multiframe_q size: {}'.format(multiFrame_queue.qsize()))







def saveMultiViewToH5():
    multiFrameNum = len(h5OutFile)
    thisFrameName = 'MultiFrame_{}'.format(str(multiFrameNum).zfill(12)) # 12 zeros is probably enough. prove me wrong, you crazy apes <3
    thisMultiFrameH5Group = h5OutFile.create_group(thisFrameName, track_order=True)

    theseFrames_list = [None]*numCams #empty list of size (numCam)
    theseTimestamps_unixEpoch = np.ndarray(numCams)

    while webcam_frames_queue.qsize() > 0:
        this_cam_frame_timestamp_tuple = webcam_frames_queue.get()
        thisCamNum = this_cam_frame_timestamp_tuple[0]
        theseFrames_list[thisCamNum]  = this_cam_frame_timestamp_tuple[1] #the image frame from thisCamera on thisMultiFrame time period
        thisTimestamp = this_cam_frame_timestamp_tuple[2] #the timestamp that this image frame was recieved by the camera
        theseTimestamps_unixEpoch[thisCamNum] = thisTimestamp #the timestamps of each frame in this multiframe (size:numCams)
        camTimestamps_list[thisCamNum] = np.append(camTimestamps_list[thisCamNum], thisTimestamp)#this'll get plotted later as a time sync diagnostic debug whosit :D
        
    thisMultiFrame = np.hstack(theseFrames_list) #horizontally stack each image into a numpy array with dimensions (imageHeight, imageWidth*numCams, 3(RGB)). Equivalent to cv2.hconcat((image0,image1,...,imageN))
    
    theseTimeStamps_fromRecStart = theseTimestamps_unixEpoch-init_time
    thisMultiFrameH5Group.create_dataset('multiFrameImage', data = thisMultiFrame)
    thisMultiFrameH5Group.create_dataset('each_timestamp_unix', data= theseTimestamps_unixEpoch)
    thisMultiFrameH5Group.create_dataset('each_timestamp_fromRecordStart', data= theseTimeStamps_fromRecStart)
    thisMultiFrameH5Group.create_dataset('mean_timestamp_unixEpoch', data= np.mean(theseTimestamps_unixEpoch))
    thisMultiFrameH5Group.create_dataset('mean_timestamp_fromRecordStart', data= np.mean(theseTimeStamps_fromRecStart))
    thisMultiFrameH5Group.create_dataset('timestamp', data= np.mean(theseTimeStamps_fromRecStart)) #this is the most intuitive timestamp to use per frame, it's a copy of the more verbosely named 'meanTimestamp_fromRecordStart'
    print('wrote ' + thisFrameName +' to H5Py - multiframe_q size: {}'.format(multiFrame_queue.qsize()))

def ShowMultiView(multiFrame_queue, outputVidObj):
    while not exit_event.is_set():
        multiIm = multiFrame_queue.get()
        outputVidObj.write(multiIm)
        cv2.imshow('m', multiIm)
        key = cv2.waitKey(1)
        if key == 27:  # exit on ESC                        
            exit_event.set()
    cv2.destroyAllWindows()
    outputVidObj.release()


if __name__ == "__main__":

    init_time = time.time()
    vidSaveFolderPath = Path('saveFrames_'+str(time.time()))
    vidSaveFolderPath.mkdir()

    format = "%(asctime)s: %(message)s"
    logging.basicConfig(filename=str(vidSaveFolderPath / 'log.txt'),format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")

    logging.info('Logging started :D')

    numCams = 3
    fps=30
    camCap_list = []
    allTimestamps = []
    camTimestamps_list = []
    camImPath_list = []
    camAx_list = []
    cam_artist = []
    multiFr = None


    for camNum in range(numCams):
        camTimestamps_list.append(np.empty(0)) #we'll put the timestamps for each camea in here
        
        logging.info('starting camera ' + str(camNum))

        if platform.system() == 'Windows':
            camCap_list.append(cv2.VideoCapture(camNum, cv2.CAP_DSHOW))
        else:
            camCap_list.append(cv2.VideoCapture(camNum, cv2.CAP_ANY))

        camCap_list[camNum].set(cv2.CAP_PROP_FPS,fps)
        camCap_list[camNum].set(cv2.CAP_PROP_EXPOSURE,-9)
        logging.info('camera '+str(camNum)+ ' started')  
        success, image = camCap_list[-1].read()
        assert success, "Camera {} failed to produce an image on startup".format(camNum)
        if multiFr is None:
            multiFr = image
        else:
            multiFr = cv2.hconcat([multiFr, image])

    #create video save object
    multiFr_height, multiFr_width, channels = multiFr.shape
    multiFrameSize = (multiFr_width, multiFr_height)
    fourcc = cv2.VideoWriter_fourcc(*'DIVX')
    outputVid_fileName = str(vidSaveFolderPath / 'outVid.mp4')
    outputVidObj = cv2.VideoWriter(outputVid_fileName, fourcc, fps, multiFrameSize)

    webcam_frames_queue = queue.Queue()
    multiFrame_queue = queue.Queue()
    exit_event = threading.Event()

    with h5py.File(str(vidSaveFolderPath/"multiFrames_saved_as_numpy_arrays.hdf5"), "w", track_order=True) as h5OutFile:
        with concurrent.futures.ThreadPoolExecutor(max_workers=numCams+1) as executor:
            # barrier = threading.Barrier(numCams, action=saveMultiViewToH5)
            barrier = threading.Barrier(numCams, action=saveMultiViewToMP4)
            for camNum, camCap in enumerate(camCap_list):
                print('starting thread for cam# '+str(camNum))
                executor.submit(CamRecordThread, camCap, webcam_frames_queue, barrier, exit_event,  camNum)
            
            executor.submit(ShowMultiView, multiFrame_queue, outputVidObj)
            # print('starting frame handler')
            # executor.submit(incoming_frames_handler, webcam_frames_queue,  exit_event)

            runtime = 10
            logging.info("Main: Record for {} seconds".format(runtime))
            time.sleep(runtime)

            exit_event.set() #send the 'Exit' signal to everyone
            print('closing streams, I guess?')

        print('closing h5 file too,  I think?')

    print('all done!')




# %% get multiFrame framerate and frameTimespread
    camTimestamps = np.stack(camTimestamps_list, axis=0) #a nice, matlaby 2d array 
    meanMultiFrameTimestamp = np.mean(camTimestamps, axis=0)
    meanMultiFrameTimespan = np.max(camTimestamps, axis=0) - np.min(camTimestamps, axis=0) #what was the timespan covered by each frame
#%%
plt.ion()
fig = plt.figure(figsize=(18,10))
max_frame_duration = .1
ax1  = plt.subplot(231, title='Camera Frame Timestamp vs Frame#', xlabel='Frame#', ylabel='Timestamp (sec)')
ax2  = plt.subplot(232, ylim=(0,max_frame_duration), title='Camera Frame Duration Trace', xlabel='Frame#', ylabel='Duration (sec)')
ax3  = plt.subplot(233, xlim=(0,max_frame_duration), title='Camera Frame Duration Histogram (count)', xlabel='Duration(s, 1ms bins)', ylabel='Probability')
ax4  = plt.subplot(234,  title='MuliFrame Timestamp vs Frame#', xlabel='Frame#', ylabel='Timestamp (sec)')
ax5  = plt.subplot(235,  ylim=(0,max_frame_duration), title='Multi Frame Duration/Span Trace', xlabel='Frame#', ylabel='Duration (sec)')
ax6  = plt.subplot(236, xlim=(0,max_frame_duration), title='MultiFrame Duration Histogram (count)', xlabel='Duration(s, 1ms bins)', ylabel='Probability')

for camNum, thisCamTimestamps in enumerate(camTimestamps_list):
    ax1.plot(thisCamTimestamps, label='Camera#'+str(camNum))
    ax1.legend()
    ax2.plot(np.diff(thisCamTimestamps),'.')    
    ax3.hist(np.diff(thisCamTimestamps), bins=np.arange(0,max_frame_duration,.001), alpha=0.5)

ax4.plot(meanMultiFrameTimestamp, color='darkslategrey', label='MultiFrame'+str(camNum))
ax5.plot(np.diff(meanMultiFrameTimestamp),'.',color='darkslategrey', label='Frame Duration')    
ax5.plot(meanMultiFrameTimespan, '.', color='orangered', label='Frame TimeSpan')    
ax5.legend()
ax6.hist(np.diff(meanMultiFrameTimestamp), bins=np.arange(0,max_frame_duration,.001), density=True, alpha=0.5, color='darkslategrey', label='Frame Duration')
ax6.hist(np.diff(meanMultiFrameTimespan), bins=np.arange(0,max_frame_duration,.001), density=True, alpha=0.5, color='orangered', label='Frame Timespan')
ax5.legend()
plt.show()
plt.savefig(str(vidSaveFolderPath / 'recording_diagnostics.png'))
f=9


# outVidObj.release()