##
##
##  ███████ ███    ███  ██████          ██████  █████  ███    ███ ███████ ██████   █████  
##  ██      ████  ████ ██              ██      ██   ██ ████  ████ ██      ██   ██ ██   ██ 
##  █████   ██ ████ ██ ██              ██      ███████ ██ ████ ██ █████   ██████  ███████ 
##  ██      ██  ██  ██ ██              ██      ██   ██ ██  ██  ██ ██      ██   ██ ██   ██ 
##  ██      ██      ██  ██████          ██████ ██   ██ ██      ██ ███████ ██   ██ ██   ██ 
##
##
#Font - ANSI Regular - https://patorjk.com/software/taag/#p=display&f=ANSI%20Regular&t=Play%20Skeleton%20Animation
                                                                                      
                                                                                      

import platform
from pathlib import Path
import time

import cv2
import numpy as np

#python rich stuff - https://rich.readthedocs.io/
from rich import print
from rich.console import Console



cap_default_parameters_dict = {
                            'exposure': -6,
                            'cap_resolution_width': 640,
                            'cap_resolution_height': 480,
                            }

class FMC_Camera:
    """ Class to open a cv2.VideoCapture object, with parts to connect to a `FMC_MutliCam` object as part of a FMC_Session. 
    Note, this class was made in service of the needs of the FreeMoCap project, at some point I'd love to develop this into a fully generic and useful 'camera' object, right now it's designed with that application (and only that application) in mind
    """
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
                cam_num=0, 
                rotation_code=None,
                frame_queue = None,
                barrier = None,
                exit_event = None,
                show_cam_stream = False,  
                rich_console = None,       
                show_console = False,       
                cap_parameters_dict = cap_default_parameters_dict,
                vid_save_path=None,  
                ):
        """Open a camera stream using `cv2.VideoCapture()`. 
        If `Windows`, use `cv2.VideoCapture(camNum, cv2.CAP_DSHOW)` to make video initialize much faster. Otherwise, use `cv2.VideoCapture(camNum, cv2.CAP_ANY)

        Args:
            camNum (int, optional): The ID of the camera to open. Defaults to 0 (i.e. the first camera it finds)
            vid_save_path (pathlib Path, optional): Where to save the video. Defaults to None.
            barrier (threading.Barrier, optional): Barrier for syncronized multicam recording. Defaults to None.
            frame_queue (queue.Queue, optional): [description]. Queue to send out images when we're recording in a thread.
        """

        self._cam_num = cam_num
        self._cam_name = 'Camera_{}'.format(str(self._cam_num).zfill(2))
        self._cam_short_name = 'cam{}'.format(self._cam_name)
        
        self._vid_cap_start_time_unix = None

        self._cap_parameters_dict = cap_parameters_dict
        
        self._rotation_code = rotation_code

        self._frame_queue = frame_queue
        self._barrier = barrier
        self._exit_event = exit_event
        self._vid_save_path = vid_save_path
        self._show_console = show_console
        self.rich_console = rich_console # a console object from the Rich python package


        if vid_save_path:
            self._vid_save_path = Path(vid_save_path)
        

        if not self.rich_console:
            self.rich_console = Console()
        
        self.open() #open VideoCapture Object

        self._show_cam_stream = show_cam_stream
        if self._show_cam_stream:
            self.show()#display camera stream

        if self._frame_queue: 
            self.run_in_thread() #launch in thread (or process?) mode
    ##   
    ##   ██████  ██████   ██████  ██████  ███████ ██████  ████████ ██ ███████ ███████ 
    ##   ██   ██ ██   ██ ██    ██ ██   ██ ██      ██   ██    ██    ██ ██      ██      
    ##   ██████  ██████  ██    ██ ██████  █████   ██████     ██    ██ █████   ███████ 
    ##   ██      ██   ██ ██    ██ ██      ██      ██   ██    ██    ██ ██           ██ 
    ##   ██      ██   ██  ██████  ██      ███████ ██   ██    ██    ██ ███████ ███████ 
    ##                                                                                
    ##                                                                                
    @property
    def cam_num(self):
        return self._cam_num
    
    @property
    def cam_name(self):
        return self._cam_name
    
    @property
    def cam_short_name(self):
        return self._cam_short_name

    @property
    def vid_save_path(self):
        return self._vid_save_path 

    @property
    def show_cam_stream(self):
        return self._show_cam_stream
    
    @show_cam_stream.setter
    def show_cam_stream(self, input_bool):
        self._show_cam_stream = input_bool

    @property
    def vid_cap_start_time_unix(self):
        return self._vid_cap_start_time_unix

    @property
    def vid_cap_timestamps_unix_ns(self): #not really a property though?
        return self._vid_cap_timestamps_unix_ns

    @property
    def show_console(self):
        return self._show_console
    
    @show_console.setter
    def show_console(self, input_bool):
        self._show_console = input_bool
    
    ###
    ###   
    ###   ███    ███ ███████ ████████ ██   ██  ██████  ██████  ███████     ███    ███  █████  ███    ██ 
    ###   ████  ████ ██         ██    ██   ██ ██    ██ ██   ██ ██          ████  ████ ██   ██ ████   ██ 
    ###   ██ ████ ██ █████      ██    ███████ ██    ██ ██   ██ ███████     ██ ████ ██ ███████ ██ ██  ██ 
    ###   ██  ██  ██ ██         ██    ██   ██ ██    ██ ██   ██      ██     ██  ██  ██ ██   ██ ██  ██ ██ 
    ###   ██      ██ ███████    ██    ██   ██  ██████  ██████  ███████     ██      ██ ██   ██ ██   ████ 
    ###                                                                                                 
    ###
    ###                                                                                                 

    def show_cam_stream(self, show_cam_stream_bool=True):
        """whether to open a window showing camera stream

        calls `self.show()` when set to `True`
        and  calls `self.close()` when set to `False` (b/c I'm too lazy to figure out how to make ti close th the display without closing the capture right now, sorry lol)

        Args:
            show_cam_stream_bool (Bool): whether to show stream (default)

        Returns:
            self
        """
        assert type(show_cam_stream_bool) == type(True), 'Input to `show_cam_stream` must be a bool'
        self._show_cam_stream = show_cam_stream_bool

        if self._show_cam_stream:
            self.show()
        else:
            self.close()

        return self._show_cam_stream
    ###   
    ###    ██████  ██████  ███████ ███    ██     ██    ██ ██ ██████       ██████  █████  ██████  
    ###   ██    ██ ██   ██ ██      ████   ██     ██    ██ ██ ██   ██     ██      ██   ██ ██   ██ 
    ###   ██    ██ ██████  █████   ██ ██  ██     ██    ██ ██ ██   ██     ██      ███████ ██████  
    ###   ██    ██ ██      ██      ██  ██ ██      ██  ██  ██ ██   ██     ██      ██   ██ ██      
    ###    ██████  ██      ███████ ██   ████       ████   ██ ██████       ██████ ██   ██ ██      
    ###                                                                                          
    ###                                                                                          
    def open(self):
        """
        Open Video Capture Object and dispaly in little video
        """

        if platform.system() == 'Windows':
            self.cv2_cap = cv2.VideoCapture(self._cam_num, cv2.CAP_DSHOW)
        else:
            self.cv2_cap = cv2.VideoCapture(self._cam_num, cv2.CAP_ANY)

        self.cv2_cap.set(cv2.CAP_PROP_EXPOSURE, self._cap_parameters_dict['exposure'])
        self.cv2_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._cap_parameters_dict['cap_resolution_width'])
        self.cv2_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._cap_parameters_dict['cap_resolution_height'])

        self.cv2_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) 


        self.video_exposure = self.cv2_cap.get(cv2.CAP_PROP_EXPOSURE)
        self.video_resolution_width = self.cv2_cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.video_resolution_height = self.cv2_cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

        if not self.cv2_cap.isOpened():
            self.rich_console.log("Camera# "+str(self._cam_num)+" failed to open :(")
            
        else:
            self.rich_console.log("Camera# "+str(self._cam_num)+"  started - Exposure:({}) - Resolution(width, height):({},{}) ".format(self.video_exposure, self.video_resolution_width, self.video_resolution_height))
            self._vid_cap_start_time_unix = time.time_ns() #the precision is aspirational, lol
            self._vid_cap_timestamps_unix_ns = np.empty(0)
    
    ###
    ###  ███████ ██   ██  ██████  ██     ██     ██    ██ ██ ██████  
    ###  ██      ██   ██ ██    ██ ██     ██     ██    ██ ██ ██   ██ 
    ###  ███████ ███████ ██    ██ ██  █  ██     ██    ██ ██ ██   ██ 
    ###       ██ ██   ██ ██    ██ ██ ███ ██      ██  ██  ██ ██   ██ 
    ###  ███████ ██   ██  ██████   ███ ███        ████   ██ ██████  
    ###
                                                                                                                                                          
    def show(self):
        """
        display the camera stream, press ESC to close (and release the `cv2_cap`)
        """
        success, image, timestamp = self.read_next_frame()
                    
        while success:
            cv2.imshow(self._cam_name, image)
            
            success, image, timestamp = self.read_next_frame()

            console_msg = self.cam_name +  " read an image at {:.4f}".format(timestamp)
            self.update_console(console_msg)
            self._vid_cap_timestamps_unix_ns = np.append(self.vid_cap_timestamps_unix_ns, timestamp)

            if self.wait_key() == 27:  # exit on ESC                        
                self.close()
            
            if cv2.getWindowProperty(self._cam_name, cv2.WND_PROP_VISIBLE) < 1: #break loop if window closed
                break   
        cv2.destroyAllWindows()

    ###  
    ###  ██████  ██    ██ ███    ██     ██ ███    ██     ████████ ██   ██ ██████  ███████  █████  ██████  
    ###  ██   ██ ██    ██ ████   ██     ██ ████   ██        ██    ██   ██ ██   ██ ██      ██   ██ ██   ██ 
    ###  ██████  ██    ██ ██ ██  ██     ██ ██ ██  ██        ██    ███████ ██████  █████   ███████ ██   ██ 
    ###  ██   ██ ██    ██ ██  ██ ██     ██ ██  ██ ██        ██    ██   ██ ██   ██ ██      ██   ██ ██   ██ 
    ###  ██   ██  ██████  ██   ████     ██ ██   ████        ██    ██   ██ ██   ██ ███████ ██   ██ ██████  
    ###                                                                                                   
    ###                                                                                                   
    def run_in_thread(self):
        """run camera in a thread
         put incoming images into an tuple containing camNum_image_timestamp_tuple and stuff it into `self._frame_queue`
        """
        # with self.rich_console.status('Camera# {} is running'.format(self.cam_num)):
        while not self._exit_event.is_set():
            try:
                success, image, timestamp = self.read_next_frame()
                cam_image_timestamp_tuple = (self.cam_num, image, timestamp)
                            
                self._frame_queue.put(cam_image_timestamp_tuple) #stuff this frame tuple packet into this camera's Queueue object

                # log_msg = self.cam_name+" got a frame at timestamp:"+ str(timestamp) + ' queue size: ' + str(self._frame_queue.qsize())
                # self.rich_console.log(log_msg)

                self._barrier.wait() #wait until other cams have grabbed a frame (and the frame_grabber has frame grabbed them)
            except:
                self.rich_console.print_exception()
        
        #shut down when 'exit_event' is tripped
        self.close()
        

    def run_in_subprocess(self):
        self.run_in_thread()

    ###     
    ###         
    ###     ███████ ████████  ██████          
    ###     ██         ██    ██               
    ###     █████      ██    ██               
    ###     ██         ██    ██               
    ###     ███████    ██     ██████ ██ ██ ██ 
    ###     
    ###     
    

    
    def __enter__(self):
        """Context manager -  No need to do anything special on start"""
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Context manager -  close `self.cv2_cap` on exit"""         
        self.close()
        return self

    def update_console(self, console_msg):
        if self.show_console:
            self.rich_console.log(console_msg) #there should be a way to log this without printing it, but I don't know how....

    def read_next_frame(self):
        """ Grab next frame, return `Tuple(success[bool, True], image, timestamp)` on success or `Tuple(success[bool, False], False, False)` on failure

        Returns:
            Success[bool]: True if frame image captured successfully
            image: the image that was recieved from the VideoCapture object
            timestamp: unix timestamp from time.time_ns()
        """
        success, image = self.cv2_cap.read()
        timestamp = time.time_ns() #the precision is aspirational, lol
        if success:
            self._vid_cap_timestamps_unix_ns = np.append(self._vid_cap_timestamps_unix_ns, time.time_ns()) #the precision is aspirational, lol

            if self._rotation_code is None:
                pass
            elif self._rotation_code == 'cv2.ROTATE_90_CLOCKWISE':                
                image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            elif self._rotation_code == 'cv2.ROTATE_90_COUNTERCLOCKWISE':                
                image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif self._rotation_code == 'cv2.ROTATE_180':                
                image = cv2.rotate(image, cv2.ROTATE_180)
            else:
                Exception, 'Invalid rotation code entered for FMC_Camera: {}'.format(self.cam_name)

            return success, image, timestamp
        else:
            return success, success, success
    
    def close(self):
        """
        close the video
        """
        self.cv2_cap.release()
        self.rich_console.log("Camera# "+str(self._cam_num)+" shutting down")

    
    def wait_key(self):

        if self.show_cam_stream:
            self._wait_key = cv2.waitKey(1)            
        else: 
            self._wait_key = 27

        return self._wait_key


### 
### ██ ███████                     ███    ███  █████  ██ ███    ██                 
### ██ ██                          ████  ████ ██   ██ ██ ████   ██                 
### ██ █████                       ██ ████ ██ ███████ ██ ██ ██  ██                 
### ██ ██                          ██  ██  ██ ██   ██ ██ ██  ██ ██                 
### ██ ██          ███████ ███████ ██      ██ ██   ██ ██ ██   ████ ███████ ███████ 
### 
###                                                                                                                                                               
if __name__ == '__main__':

    with FMC_Camera() as cam:
        console = Console() #create Rich console to catch and print exceptions
        try:
            while True:
                cam.show()
                break
        except Exception:
            console.print_exception()

