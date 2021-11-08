##   
##   
##   ███████ ███    ███  ██████     ███    ███ ██    ██ ██      ████████ ██        ██████  █████  ███    ███ ███████ ██████   █████  
##   ██      ████  ████ ██          ████  ████ ██    ██ ██         ██    ██       ██      ██   ██ ████  ████ ██      ██   ██ ██   ██ 
##   █████   ██ ████ ██ ██          ██ ████ ██ ██    ██ ██         ██    ██ █████ ██      ███████ ██ ████ ██ █████   ██████  ███████ 
##   ██      ██  ██  ██ ██          ██  ██  ██ ██    ██ ██         ██    ██       ██      ██   ██ ██  ██  ██ ██      ██   ██ ██   ██ 
##   ██      ██      ██  ██████     ██      ██  ██████  ███████    ██    ██        ██████ ██   ██ ██      ██ ███████ ██   ██ ██   ██ 
##                                                                                                                                   
##                                                                                                                                   
#Font - ANSI Regular - https://patorjk.com/software/taag/#p=display&f=ANSI%20Regular&t=Play%20Skeleton%20Animation



from rich.repr import T
from FMC_Camera import FMC_Camera

import concurrent.futures
import logging
import queue
import threading
import pathos.multiprocessing as pathos_mp
from pathos.helpers import mp as pathos_mp_helper
import time
import platform
import datetime

import cv2
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

from rich import print
from rich import inspect
from rich.progress import track
from rich.traceback import install
install(show_locals=True)
from rich.console import Console
rich_console = Console()
from rich.progress import track


class FMC_MultiCamera:
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
                rotation_codes_list = None,
                show_multi_cam_stream_bool = True,
                save_multi_cam_to_mp4 = False,
                save_each_cam_to_mp4 = True,
                save_to_h5 = False,
                save_log_file = False
                ):
        
        self._init_start_time = time.time_ns()#the precision is aspirational, lol

        if rec_name is None:
            self._rec_name = datetime.datetime.now().strftime("FMC_MultiCamRecording_%Y-%m-%d_%H_%M_%S")
        else:
            self._rec_name = rec_name


        if save_path is None:
            self._save_path = Path('data/' + self._rec_name)
        else:
            self._save_path = Path(save_path)
        
        if save_path or save_multi_cam_to_mp4 or save_to_h5 or save_log_file or save_each_cam_to_mp4:
            self._save_path.mkdir(parents=True, exist_ok=True)
            self._path_to_log_file = Path(str(self._save_path / self._rec_name) + '_log.txt')

        self._save_multi_cam_to_mp4 = save_multi_cam_to_mp4        
        if self._save_multi_cam_to_mp4:            
            self._output_multi_cam_video_object = None #build this after we get the first multi_frame_image

        self._save_each_cam_to_mp4 = save_each_cam_to_mp4
        if self._save_each_cam_to_mp4:            
            self._each_cam_video_writer_object_list = None #build this after we get the first multi_frame_image


        # log_file_obj = open(self._path_to_log_file,'w+')
        # rich_console = Console(file=log_file_obj)
        rich_console = Console()

        self._num_cams = num_cams
        self._cams_to_use_list = cams_to_use_list
        
        if rotation_codes_list:
            self._rotation_codes_list = rotation_codes_list
        else:
            self._rotation_codes_list = [None] * self.num_cams            

        self._show_multi_cam_stream_bool = show_multi_cam_stream_bool
        
        
        rich_console.rule('Starting FreeMoCap MultiCam!')


        

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

    #################################################################
    ###   
    ###   
    ###   ███████ ████████  █████  ██████  ████████ 
    ###   ██         ██    ██   ██ ██   ██    ██    
    ###   ███████    ██    ███████ ██████     ██    
    ###        ██    ██    ██   ██ ██   ██    ██    
    ###   ███████    ██    ██   ██ ██   ██    ██    
    ###                                             
    ###                                             
    ###                                                                
    ###                                                                    
    def start(self, standalone_mode=False):
        self.standalone_mode = standalone_mode
        if self.cams_to_use_list is None:
            self.find_available_cameras()
                
        
        # pathos_pool = ProcessPool(nodes=1)
        # pathos_pool.map(self.start_multi_cam_thread_pool)
        # self.start_multi_cam_thread_pool() #threads are mostly fine, but I think processes will be better eventually? 
        self.start_multi_cam_process_pool()
        if standalone_mode:
            self.create_diagnostic_images()

    

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
        for camNum in range(num_cams_to_check):#track(range(num_cams_to_check), description='[green]Finding available cameras...' ):
            print('ATTEMPTING TO OPEN CAMERA AT PORT# {}'.format(camNum))
            cap =  cv2.VideoCapture(camNum, capBackend)
            if cap.isOpened():
                rich_console.print('SUCCESS - CAMERA FOUND at # {}'.format(camNum), style="bold cyan")
                self._cams_to_use_list.append(camNum)
                cap.release()
            else:
                rich_console.print('No CAMERA FOUND at # {}'.format(camNum), style="magenta")

        rich_console.print("Found cameras at ", self._cams_to_use_list)
        
        self.num_cams = len(self._cams_to_use_list)
        return self.cams_to_use_list
    
###   
###   
###   ███████ ████████  █████  ██████  ████████     ██████  ██████   ██████   ██████ ███████ ███████ ███████     ██████   ██████   ██████  ██      
###   ██         ██    ██   ██ ██   ██    ██        ██   ██ ██   ██ ██    ██ ██      ██      ██      ██          ██   ██ ██    ██ ██    ██ ██      
###   ███████    ██    ███████ ██████     ██        ██████  ██████  ██    ██ ██      █████   ███████ ███████     ██████  ██    ██ ██    ██ ██      
###        ██    ██    ██   ██ ██   ██    ██        ██      ██   ██ ██    ██ ██      ██           ██      ██     ██      ██    ██ ██    ██ ██      
###   ███████    ██    ██   ██ ██   ██    ██        ██      ██   ██  ██████   ██████ ███████ ███████ ███████     ██       ██████   ██████  ███████ 
###                                                                                                                                                
###                                                                                                                                                
###   
    def start_multi_cam_process_pool(self):
        """
        reates a ProcessPoolExecutor that creates an `FMC_Camera` object for each camera in `self.cams_to_use_list` and sets each to trigger `run_in_process`  mode (which just passes to `run_in_thread` mode)

        """
        mrManager = pathos_mp_helper.Manager()
        self.cam_frame_queue = mrManager.Queue(maxsize=self.num_cams)
        self.multi_cam_tuple_queue = mrManager.Queue()
        self.barrier = mrManager.Barrier(self.num_cams+1) #each cam + one more for the frame grabber
        self.exit_event = mrManager.Event()

        self._each_cam_timestamps_unix_ns = None
        self._cam_process = [None] * self.num_cams

        rich_console.rule('starting multi_cam_process_pool')

        in_frame_q_list = [self.cam_frame_queue]*self.num_cams
        in_barrier_list = [self.barrier]*self.num_cams
        in_exit_event_list = [self.exit_event]*self.num_cams
        # nsole_list = [self.rich_console]*self.num_cams


        num_jobs = self.num_cams
        with pathos_mp.ProcessingPool(num_jobs) as self.cam_process_pool: 
            self.cam_process_pool.amap(
                        FMC_Camera, 
                        tuple(self.cams_to_use_list), 
                        tuple(self._rotation_codes_list),
                        tuple(in_frame_q_list), 
                        tuple(in_barrier_list), 
                        tuple(in_exit_event_list),
                        )
            self.incoming_tuple_grabber_thread = threading.Thread(target=self.grab_incoming_cam_tuples, name='Incoming Frame Tuple Grabber Thread')
            self.incoming_tuple_grabber_thread.start()
            if self._show_multi_cam_stream_bool or self.standalone_mode:
                self.show_multi_cam_opencv()



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

        # self.show_multi_cam_cv2()

        while not self.exit_event.is_set():
            self.barrier.wait() #wait until each camera has grabbed an image and tagged their `barrier.wait()` signals

            these_images_list = [None]*self.num_cams #empty list of size (numCam)
            this_multi_cam_tuple_as_a_list = [None]*self.num_cams
            these_timestamps = np.ndarray(self.num_cams)

            for cam_num in range(self.num_cams):
                this_cam_image_timestamp_tuple = self.cam_frame_queue.get()
                this_cam_num = this_cam_image_timestamp_tuple[0]
                this_cam_index = self.cams_to_use_list.index(this_cam_num)
                these_images_list[this_cam_index] = this_cam_image_timestamp_tuple[1]
                these_timestamps[this_cam_index] = this_cam_image_timestamp_tuple[2]
                this_multi_cam_tuple_as_a_list[this_cam_index] = this_cam_image_timestamp_tuple
            
            this_multi_cam_tuple = tuple(this_multi_cam_tuple_as_a_list)

            if self._each_cam_timestamps_unix_ns is None:
                self._each_cam_timestamps_unix_ns =  these_timestamps
            else:
                self._each_cam_timestamps_unix_ns =  np.vstack((self._each_cam_timestamps_unix_ns, these_timestamps)) #result will be numpy array with `num_frames` rows and `num_cams` columns

            self.multi_cam_tuple_queue.put(this_multi_cam_tuple, np.mean(these_timestamps))
            
            
            # rich_console.log('Created a multi_cam_tuple - queue size: {}'.format(self.multi_cam_tuple_queue.qsize()))
    
    def stitch_multicam_image(self, multi_cam_tuple):
        """Take in a multi-cam-tuple (containing images from each camera during the period of time defined by the attached timestamps)

        Args:
            multi_cam_tuple (tuple of tuples): The multi_cam_tuple produced by `self.grab_incoming_cam_tuples()` comprising a timestamp and a tuple from each of the cameras. Each camera's tuple consists of the camera's ID/Number, the image frame, and the timestamp that frame was recorded. The multi-camtimestamp is the mean of each of the timestamps from the individual cameras. 
        Returns:
            multi_cam_image: an image of size camera_res_width*num_cams x camera_res_height The images are synchronized within the precision defined by the timestamps included in the individual camera tuples. 
        """

        these_images_list = [None]*self.num_cams #empty list of size (numCam)
           
           

        for this_cam_num in range(self.num_cams):                                
            these_images_list[this_cam_num] = multi_cam_tuple[this_cam_num][1] #and that's how you navigate nested tuples, lol                                
        
        multi_cam_image = np.hstack(these_images_list)  #create multiFrame_image by stitching together (horizontally stacking) incoming camera images (matrices)
        return multi_cam_image

        # rich_console.log('Created a multi_cam_image - queue size: {}'.format(self.multi_cam_tuple_queue.qsize()))

    ###                  
    ###  
    ###  ███████ ██   ██  ██████  ██     ██     ██    ██ ██ ██████  
    ###  ██      ██   ██ ██    ██ ██     ██     ██    ██ ██ ██   ██ 
    ###  ███████ ███████ ██    ██ ██  █  ██     ██    ██ ██ ██   ██ 
    ###       ██ ██   ██ ██    ██ ██ ███ ██      ██  ██  ██ ██   ██ 
    ###  ███████ ██   ██  ██████   ███ ███        ████   ██ ██████  
    ###                                                             
    ###                                                             6
    
    def show_multi_cam_opencv(self):
        """display multi_cam_image using `cv2.imshow` and maybe save it to mp4, who knows?
        """
        rich_console.rule('Launching Multi Cam Viewer')
        while not self.exit_event.is_set():   
            if not self.multi_cam_tuple_queue.empty():
                
                this_multi_cam_tuple = self.multi_cam_tuple_queue.get()
                self.save_synchronized_videos(this_multi_cam_tuple)
                this_multi_cam_image = self.stitch_multicam_image(this_multi_cam_tuple)

                if self._save_multi_cam_to_mp4:
                    if self._output_multi_cam_video_object is None:
                        self.initialize_multi_cam_output_video(this_multi_cam_image)
                    

                    self._output_multi_cam_video_object.write(this_multi_cam_image)
                
                if self._save_each_cam_to_mp4:
                    if self._each_cam_video_writer_object_list is None:
                        self.initialize_each_cam_output_video(this_multi_cam_tuple)
                    
                    for this_cam_num in range(self.num_cams):
                        self._each_cam_video_writer_object_list[this_cam_num].write(this_multi_cam_tuple[this_cam_num][1])

                cv2.imshow(self._rec_name, this_multi_cam_image)
                key = cv2.waitKey(1)

                if key == 27:  # exit on ESC                        
                    self.exit_event.set()
                
                if cv2.getWindowProperty(self._rec_name, cv2.WND_PROP_VISIBLE) < 1: #break loop if window closed
                    self.exit_event.set()   

        cv2.destroyAllWindows()
        if self._save_multi_cam_to_mp4:
            self._output_multi_cam_video_object.release()
            if self._save_each_cam_to_mp4:
                for this_cam_num in range(self.num_cams):
                    self._each_cam_video_writer_object_list[this_cam_num].release()

        rich_console.rule('Shutting down MultiCamera Viewer')
        self.exit_event.set() #send the 'Exit' signal to everyone.
    
    def save_synchronized_videos(self, multi_cam_tuple):
        """save camera streams into individual videos (that can be processed with pre-alpha freemocap"""
        these_images_list = [None]*self.num_cams #empty list of size (numCam)
           
        for this_cam_num in range(self.num_cams):                                
            this_cam_image = multi_cam_tuple[this_cam_num][1] #and that's how you navigate nested tuples, lol         

        
        


    ###  
    ###          
    ###  ██ ███    ██ ██ ████████      ██████  ██    ██ ████████     ██    ██ ██ ██████  
    ###  ██ ████   ██ ██    ██        ██    ██ ██    ██    ██        ██    ██ ██ ██   ██ 
    ###  ██ ██ ██  ██ ██    ██        ██    ██ ██    ██    ██        ██    ██ ██ ██   ██ 
    ###  ██ ██  ██ ██ ██    ██        ██    ██ ██    ██    ██         ██  ██  ██ ██   ██ 
    ###  ██ ██   ████ ██    ██         ██████   ██████     ██          ████   ██ ██████  
    ###                                                                                  
    ###                                                                                  

    def initialize_multi_cam_output_video(self, multi_cam_image):
        """use  the multi_cam_image to initialize the video
            multicam image will be of size  [cam_resolution_width*num_cams by cam_resolution_height]
        Args:
            multi_cam_image ([type]): [description]
        """
        #create video save object
        self._multi_cam_image_height, self._multi_cam_image_width, channels = multi_cam_image.shape

        self.multi_cam_image_size = ( self._multi_cam_image_width, self._multi_cam_image_height)
        fourcc = cv2.VideoWriter_fourcc(*'DIVX')
        self._output_multi_cam_vid_fileName = str(self._save_path / self._rec_name) + '_outVid.mp4'
        fps = 25 #this is a bad and stupid guess, but it's actually kinda tricky to guess what is the right thing to put here. I'll fix this later and expect videos to be a bit faster than usual :(
        self._output_multi_cam_video_object = cv2.VideoWriter(self._output_multi_cam_vid_fileName, fourcc, fps, self.multi_cam_image_size)
    
    
    def initialize_each_cam_output_video(self, multi_cam_tuple):
        
        self._each_cam_video_writer_object_list=[None]*self.num_cams
        self._each_cam_video_filename_list=[None]*self.num_cams

        self.syncedVidsPath = self._save_path / self._rec_name / 'SyncedVids'
        self.syncedVidsPath.mkdir(parents=True)

        for this_cam_num in range(self.num_cams):
            #create video save object
            this_cam_image = multi_cam_tuple[this_cam_num][1]
            this_cam_timestamp_unix_ns = multi_cam_tuple[this_cam_num][2]
            self._cam_image_height, self._cam_image_width, channels = this_cam_image.shape

            self._cam_image_size = ( self._cam_image_width, self._cam_image_height)
            fourcc = cv2.VideoWriter_fourcc(*'DIVX')
            
            self._each_cam_video_filename_list[this_cam_num] = str(self.syncedVidsPath) + '/Cam_'+str(this_cam_num)+'_synchronized.mp4'
            fps = 25 #this is a bad and stupid guess, but it's actually kinda tricky to guess what is the right thing to put here. I'll fix this later and expect videos to be a bit faster than usual :(
            self._each_cam_video_writer_object_list[this_cam_num] = cv2.VideoWriter(self._each_cam_video_filename_list[this_cam_num], fourcc, fps, self._cam_image_size)
    ##   
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
        try:
            camTimestamps = (self.each_cam_timestamps_unix_ns-self.init_start_time)/1e9 #subtract start time and convert to sec
            
            npy_save_path = self._save_path /'multi_cam_timestamps_frameNum_camNum.npy'
            np.save(str(npy_save_path), camTimestamps)
            rich_console.log('saving timestamp data to - ' + str(npy_save_path) )
            
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
        
            fig_save_path = self._save_path / 'recording_diagnostics.png'
            plt.savefig(str(fig_save_path))  
            rich_console.log('Saving diagnostic figure to - '+str(fig_save_path))
            plt.show()
            plt.waitforbuttonpress()
        except:
            rich_console.print_exception()
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
    pathos_mp_helper.freeze_support()
    console = Console() #create rich console to catch and print exceptions

    import socket
    this_computer_name = socket.gethostname()

    if this_computer_name=='jon-hallway-XPS-8930':
        freemocap_data_path = Path('/home/jon/Dropbox/FreeMoCapProject/FreeMocap_Data')
        in_rotation_codes_list = ['cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', ]
    else:
        freemocap_data_path=None
        in_rotation_codes_list=None

    try:
        multi_cam = FMC_MultiCamera(save_path=str(freemocap_data_path), rotation_codes_list=in_rotation_codes_list)
        multi_cam.start(standalone_mode=True)        
                                 
    except Exception:
        console.print_exception()


