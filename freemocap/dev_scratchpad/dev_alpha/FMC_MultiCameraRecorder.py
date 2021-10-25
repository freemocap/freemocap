##   
##   
##   ███████ ███    ███  ██████     ███    ███ ██    ██ ██      ████████ ██        ██████  █████  ███    ███ ███████ ██████   █████  
##   ██      ████  ████ ██          ████  ████ ██    ██ ██         ██    ██       ██      ██   ██ ████  ████ ██      ██   ██ ██   ██ 
##   █████   ██ ████ ██ ██          ██ ████ ██ ██    ██ ██         ██    ██ █████ ██      ███████ ██ ████ ██ █████   ██████  ███████ 
##   ██      ██  ██  ██ ██          ██  ██  ██ ██    ██ ██         ██    ██       ██      ██   ██ ██  ██  ██ ██      ██   ██ ██   ██ 
##   ██      ██      ██  ██████     ██      ██  ██████  ███████    ██    ██        ██████ ██   ██ ██      ██ ███████ ██   ██ ██   ██ 
##                                                                                                                                   
##                                                                                                                                   


from os import mkdir
from fmc_camera import FMC_Camera

import concurrent.futures
import logging
import queue
import threading
import time
import platform
import datetime

import cv2
import matplotlib.pyplot as plt
import numpy as np
import h5py
from pathlib import Path

from rich import print
from rich import inspect
from rich.progress import track
from rich.traceback import install
install(show_locals=True)
from rich.console import Console
from rich.progress import track


class FMC_MultiCameraRecorder:
    ##  
    ##  
    ##                  ██ ███    ██ ██ ████████                 
    ##                  ██ ████   ██ ██    ██                    
    ##                  ██ ██ ██  ██ ██    ██                    
    ##                  ██ ██  ██ ██ ██    ██                    
    ##  ███████ ███████ ██ ██   ████ ██    ██    ███████ ███████ 
    ##                                                           
    ##  
    ##  
    def __init__(
                self,
                rec_name = None,
                save_path = None,
                num_cams = 0,
                cams_to_use_list = None,
                show_multi_cam_stream = True,
                save_to_mp4 = True,
                save_to_h5 = False,
                save_log_file = False
                ):
        
        self._init_start_time = time.time_ns()#the precision is aspirational, lol

        if rec_name is None:
            self._rec_name = datetime.datetime.now().strftime("FMC_MultiCamRecording_%Y-%b-%d_%H_%M_%S")
        else:
            self._rec_name = rec_name


        if save_path is None:
            self._save_path = Path('data/' + self._rec_name)
        else:
            self._save_path = Path(save_path)
        
        if save_path or save_to_mp4 or save_to_h5 or save_log_file:
            self._save_path.mkdir(parents=True)
            self._path_to_log_file = Path(str(self._save_path / self._rec_name) + '_log.txt')

        self._save_to_mp4 = save_to_mp4
        if self._save_to_mp4:            
            self._output_video_object = None #build this after we get the first multi_frame_image

        # log_file_obj = open(self._path_to_log_file,'w+')
        # self.rich_console = Console(file=log_file_ob)
        self.rich_console = Console()

        self._num_cams = num_cams
        self._cams_to_use_list = cams_to_use_list
        
        self.exit_event = threading.Event()

        
        
        self.rich_console.rule('Starting FreeMoCap MultiCam Recorder!')

        if self.cams_to_use_list is None:
            self.find_available_cameras()
        

        self.start_multi_cam_thread_pool()
    
    ###   
    ###   
    ###   ██████  ██████   ██████  ██████  ███████ ██████  ████████ ██ ███████ ███████ 
    ###   ██   ██ ██   ██ ██    ██ ██   ██ ██      ██   ██    ██    ██ ██      ██      
    ###   ██████  ██████  ██    ██ ██████  █████   ██████     ██    ██ █████   ███████ 
    ###   ██      ██   ██ ██    ██ ██      ██      ██   ██    ██    ██ ██           ██ 
    ###   ██      ██   ██  ██████  ██      ███████ ██   ██    ██    ██ ███████ ███████ 
    ###                                                                                
    ###                                                                                

    @property
    def num_cams(self):
        """How many cameras to use"""        
        return self._num_cams

    @num_cams.setter
    def num_cams(self, num_cams_input):
        """Define how many cameras to use"""
        self._num_cams = num_cams_input        

    @property
    def cams_to_use_list(self):
        """ a list denoting which camera IDs to use.
         If both this and `num_cams` are set to default value (`0` and `None`, respectively), use all available cameras).
         """
        return self._cams_to_use_list

    @property
    def init_start_time(self):
        """Time that this object was initialized (UNIX Epoch time from `time.time_ns())

        Returns:
            float: time this object was created (UNIX Epoch time from `time.time_ns())
        """
        return self._init_start_time
    
    @property
    def each_cam_timestamps_unix_ns(self): #not really a property though?
        return self._each_cam_timestamps_unix_ns
    ###   
    ###   
    ###   ███    ███ ███████ ████████ ██   ██  ██████  ██████  ███████ 
    ###   ████  ████ ██         ██    ██   ██ ██    ██ ██   ██ ██      
    ###   ██ ████ ██ █████      ██    ███████ ██    ██ ██   ██ ███████ 
    ###   ██  ██  ██ ██         ██    ██   ██ ██    ██ ██   ██      ██ 
    ###   ██      ██ ███████    ██    ██   ██  ██████  ██████  ███████ 
    ###                                                                
    ###                                                                    


    def find_available_cameras(self):
        """find available webcams and return IDs in list."""
        
        if self.num_cams == 0:
            num_cams_to_check = 20 #man, i HOPE you're out there trying to record from more than 20 cameras!!!
        else:
            num_cams_to_check = self.num_cams
        
        if platform.system() == 'Windows':
            capBackend = cv2.CAP_DSHOW
        else:
            capBackend = cv2.CAP_ANY

        self._cams_to_use_list = []
        for camNum in track(range(num_cams_to_check), description='[green]Finding available cameras...' ):
            cap =  cv2.VideoCapture(camNum, capBackend)
            if cap.isOpened():
                self._cams_to_use_list.append(camNum)
            cap.release()
        console.print("Found cameras at ", self._cams_to_use_list)
        
        self.num_cams = len(self._cams_to_use_list)
        return self.cams_to_use_list
    ###  
    ###  
    ###  ███████ ████████  █████  ██████  ████████     ████████ ██   ██ ██████  ███████  █████  ██████      ██████   ██████   ██████  ██      
    ###  ██         ██    ██   ██ ██   ██    ██           ██    ██   ██ ██   ██ ██      ██   ██ ██   ██     ██   ██ ██    ██ ██    ██ ██      
    ###  ███████    ██    ███████ ██████     ██           ██    ███████ ██████  █████   ███████ ██   ██     ██████  ██    ██ ██    ██ ██      
    ###       ██    ██    ██   ██ ██   ██    ██           ██    ██   ██ ██   ██ ██      ██   ██ ██   ██     ██      ██    ██ ██    ██ ██      
    ###  ███████    ██    ██   ██ ██   ██    ██           ██    ██   ██ ██   ██ ███████ ██   ██ ██████      ██       ██████   ██████  ███████ 
    ###                                                                                                                                       
    ###                                                                                                                                       

    def start_multi_cam_thread_pool(self):
        """creates a threading.ThreadPoolExecutor that creates an `FMC_Camera` object for each camera in `self.cams_to_use_list` and sets each to trigger `run_in_thread` mode

            NOTE - Eventually I want these to be in different processes, I think?
        """
        self.cam_frame_queue = queue.Queue(maxsize=self.num_cams)
        self.multi_cam_image_queue = queue.Queue()

        self._each_cam_timestamps_unix_ns = None
        self._cam_thread = [None] * self.num_cams

        self.rich_console.rule('starting multi_cam_thread_pool')

        while not self.exit_event.is_set():
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_cams+1) as executor:
                self.thread_barrier = threading.Barrier(self.num_cams, action=self.grab_incoming_cam_tuples)
                for  this_cam_num in self.cams_to_use_list: #i feel like there is some cooler way to do this using 'map' and 'zip' or whatever, but this feels easier on the ol' brain noggin lol
                    self._cam_thread[this_cam_num] = executor.submit(FMC_Camera, cam_num=this_cam_num, frame_queue = self.cam_frame_queue, thread_barrier = self.thread_barrier, exit_event = self.exit_event, console=self.rich_console)
                executor.submit(self.show_multi_cam_cv2)
    
    ###  
    ###  
    ###   ██████  ██████   █████  ██████      ██ ███    ██  ██████  ██████  ███    ███ ██ ███    ██  ██████      ████████ ██    ██ ██████  ██      ███████ ███████ 
    ###  ██       ██   ██ ██   ██ ██   ██     ██ ████   ██ ██      ██    ██ ████  ████ ██ ████   ██ ██              ██    ██    ██ ██   ██ ██      ██      ██      
    ###  ██   ███ ██████  ███████ ██████      ██ ██ ██  ██ ██      ██    ██ ██ ████ ██ ██ ██ ██  ██ ██   ███        ██    ██    ██ ██████  ██      █████   ███████ 
    ###  ██    ██ ██   ██ ██   ██ ██   ██     ██ ██  ██ ██ ██      ██    ██ ██  ██  ██ ██ ██  ██ ██ ██    ██        ██    ██    ██ ██      ██      ██           ██ 
    ###   ██████  ██   ██ ██   ██ ██████      ██ ██   ████  ██████  ██████  ██      ██ ██ ██   ████  ██████         ██     ██████  ██      ███████ ███████ ███████ 
    ###                                                                                                                                                            
    ###                                                                                                                                                            


    def grab_incoming_cam_tuples(self):
        """grab incoming cam_tuples, put them into a multi_cam_tuple and stuff that into the multi_cam_tuple_queue"""
        
        these_images_list = [None]*self.num_cams #empty list of size (numCam)
        these_timestamps = np.ndarray(self.num_cams)

        for cam_num in range(self.num_cams):
            this_cam_image_timestamp_tuple = self.cam_frame_queue.get()
            this_cam_num = this_cam_image_timestamp_tuple[0]
            these_images_list[this_cam_num] = this_cam_image_timestamp_tuple[1]
            these_timestamps[this_cam_num] = this_cam_image_timestamp_tuple[2]
        
        if self._each_cam_timestamps_unix_ns is None:
            self._each_cam_timestamps_unix_ns =  these_timestamps
        else:
            self._each_cam_timestamps_unix_ns =  np.vstack((self._each_cam_timestamps_unix_ns, these_timestamps)) #result will be numpy array with `num_frames` rows and `num_cams` columns


        multi_cam_image = np.hstack(these_images_list)  #create multiFrame_image by stitching together incoming camera images
        self.multi_cam_image_queue.put(multi_cam_image)
        # self.rich_console.log('Created a multi_cam_image')
    
    ###                  
    ###  
    ###  ███████ ██   ██  ██████  ██     ██     ██    ██ ██ ██████  
    ###  ██      ██   ██ ██    ██ ██     ██     ██    ██ ██ ██   ██ 
    ###  ███████ ███████ ██    ██ ██  █  ██     ██    ██ ██ ██   ██ 
    ###       ██ ██   ██ ██    ██ ██ ███ ██      ██  ██  ██ ██   ██ 
    ###  ███████ ██   ██  ██████   ███ ███        ████   ██ ██████  
    ###                                                             
    ###                                                             
    
    def show_multi_cam_cv2(self):
        """display multi_cam_image using `cv2.imshow` and maybe save it to mp4, who knows?
        """
        self.rich_console.log('Launching Multi Cam Viewer')
        while not self.exit_event.is_set():   
            if not self.multi_cam_image_queue.empty():
                multi_cam_image = self.multi_cam_image_queue.get()

                if self._save_to_mp4:
                    if self._output_video_object is None:
                        self.initialize_video(multi_cam_image)
                    self._output_video_object.write(multi_cam_image)

                cv2.imshow(self._rec_name, multi_cam_image)
                key = cv2.waitKey(1)

                if key == 27:  # exit on ESC                        
                    self.exit_event.set()
                
                if cv2.getWindowProperty(self._rec_name, cv2.WND_PROP_VISIBLE) < 1: #break loop if window closed
                    self.exit_event.set()   

        cv2.destroyAllWindows()
        if self._save_to_mp4:
            self._output_video_object.release()
        self.rich_console.log('Shutting down MultiCamera Viewer')
        selfmulti_cam.exit_event.set() #send the 'Exit' signal to everyone   
    
    ###  
    ###          
    ###  ██ ███    ██ ██ ████████      ██████  ██    ██ ████████     ██    ██ ██ ██████  
    ###  ██ ████   ██ ██    ██        ██    ██ ██    ██    ██        ██    ██ ██ ██   ██ 
    ###  ██ ██ ██  ██ ██    ██        ██    ██ ██    ██    ██        ██    ██ ██ ██   ██ 
    ###  ██ ██  ██ ██ ██    ██        ██    ██ ██    ██    ██         ██  ██  ██ ██   ██ 
    ###  ██ ██   ████ ██    ██         ██████   ██████     ██          ████   ██ ██████  
    ###                                                                                  
    ###                                                                                  

    def initialize_video(self, multi_cam_image):
        """use  the multi_cam_image to initialize the video
            multicam image will be of size  [cam_resolution_width*num_cams by cam_resolution_height]
        Args:
            multi_cam_image ([type]): [description]
        """
        #create video save object
        self._multi_cam_image_height, self._multi_cam_image_width, channels = multi_cam_image.shape

        self.multi_cam_image_size = ( self._multi_cam_image_width, self._multi_cam_image_height)
        fourcc = cv2.VideoWriter_fourcc(*'DIVX')
        self._outputVid_fileName = str(self._save_path / self._rec_name) + '_outVid.mp4'
        fps = 30 #this is a bad and stupid guess, but it's actually kinda tricky to guess what is the right thing to put here. I'll fix this later and expect videos to be a bit faster than usual :(
        self._output_video_object = cv2.VideoWriter(self._outputVid_fileName, fourcc, fps, self.multi_cam_image_size)
    ##   
    ##   
    ##   ██████  ██       ██████  ████████     ████████ ██ ███    ███ ███████ ███████ ████████  █████  ███    ███ ██████  ███████ 
    ##   ██   ██ ██      ██    ██    ██           ██    ██ ████  ████ ██      ██         ██    ██   ██ ████  ████ ██   ██ ██      
    ##   ██████  ██      ██    ██    ██           ██    ██ ██ ████ ██ █████   ███████    ██    ███████ ██ ████ ██ ██████  ███████ 
    ##   ██      ██      ██    ██    ██           ██    ██ ██  ██  ██ ██           ██    ██    ██   ██ ██  ██  ██ ██           ██ 
    ##   ██      ███████  ██████     ██           ██    ██ ██      ██ ███████ ███████    ██    ██   ██ ██      ██ ██      ███████ 
    ##                                                                                                                            
    ##                                                                                                                            

    def create_diagnostic_images(self):
        """plot some diagnostics to assess quality of camera sync"""

        camTimestamps = (self.each_cam_timestamps_unix_ns-self.init_start_time)/1e9 #subtract start time and convert to sec
        np.save(str(self._save_path /'multi_cam_timestamps_frameNum_camNum.npy'), camTimestamps)
        meanMultiFrameTimestamp = np.mean(camTimestamps, axis=1)
        meanMultiFrameTimespan = np.max(camTimestamps, axis=1) - np.min(camTimestamps, axis=1) #what was the timespan covered by each frame
        plt.ion()
        fig = plt.figure(figsize=(18,10))
        max_frame_duration = .1
        ax1  = plt.subplot(231, title='Camera Frame Timestamp vs Frame#', xlabel='Frame#', ylabel='Timestamp (sec)')
        ax2  = plt.subplot(232, ylim=(0,max_frame_duration), title='Camera Frame Duration Trace', xlabel='Frame#', ylabel='Duration (sec)')
        ax3  = plt.subplot(233, xlim=(0,max_frame_duration), title='Camera Frame Duration Histogram (count)', xlabel='Duration(s, 1ms bins)', ylabel='Probability')
        ax4  = plt.subplot(234,  title='MuliFrame Timestamp vs Frame#', xlabel='Frame#', ylabel='Timestamp (sec)')
        ax5  = plt.subplot(235,  ylim=(0,max_frame_duration), title='Multi Frame Duration/Span Trace', xlabel='Frame#', ylabel='Duration (sec)')
        ax6  = plt.subplot(236, xlim=(0,max_frame_duration), title='MultiFrame Duration Histogram (count)', xlabel='Duration(s, 1ms bins)', ylabel='Probability')

        for camNum in range(self.num_cams):
            thisCamTimestamps = camTimestamps[:,camNum]
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
      
        plt.savefig(str(self._save_path / 'recording_diagnostics.png'))  
        plt.show()
        f=9
    
    ### 
    ### ███████ ████████  ██████              
    ### ██         ██    ██                   
    ### █████      ██    ██                   
    ### ██         ██    ██                   
    ### ███████    ██     ██████     ██ ██ ██ 
    ###                                       
    
        def __enter__(self):
        """Context manager -  No need to do anything special on start"""
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Context manager -  on exit, set `self.exit_event` to activate shutdown sequence """
        self.create_diagnostic_images()
        return self
###   
###               
###   ██ ███████                     ███    ███  █████  ██ ███    ██                 
###   ██ ██                          ████  ████ ██   ██ ██ ████   ██                 
###   ██ █████                       ██ ████ ██ ███████ ██ ██ ██  ██                 
###   ██ ██                          ██  ██  ██ ██   ██ ██ ██  ██ ██                 
###   ██ ██          ███████ ███████ ██      ██ ██   ██ ██ ██   ████ ███████ ███████ 
###                                                                                  
###                                                                                  


if __name__ == '__main__':
    console = Console() #create rich console to catch and print exceptions
    try:
        with FMC_MultiCameraRecorder() as multi_cam:
            runtime = 10
            logging.info("Main: Record for {} seconds".format(runtime))
            time.sleep(runtime)
            print('shutting down MultiCamRecorder')
                                 
    except Exception:
        console.print_exception()


