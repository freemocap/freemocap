
____
 # FMC_MultiCamera
>
>   A class to launch a 'multi_camera' which acts like a single camera but pulls synchronized images from multiple USB webcams
> 
## Class definition and contents


## Run as __Main__ file - Code sequence chart

```mermaid
%%{init: {"securityLevel": "loose","theme": "base", "themeVariables": { "primaryColor": "#fff4dd", "primaryBorderColor":"#Fffff0","primaryTextColor":"#FFF", "actorBkg":"#FF0000", "loopTextColor":"#fff000","activationBkgColor":"#000FFF", "sequenceNumberColor":"#000000"}}}%%
sequenceDiagram
autonumber
    participant M as __Main__
    participant I as FMC_MultiCamera.__init__()
    participant S as multicam.start(standalone_mode=True)
    participant F as self.find_available_cameras()
    participant P as self.start_multi_cam_process_pool()
    participant CI as FMC_Camera.__init__()
    participant CT as FMC_Camera.run_in_thread()
    participant CR as FMC_Camera.read_next_frame()
    participant FQ as FMC_Camera._frame_queue()
    participant FG as FMC_MultiCamera.grab_incoming_cam_tuples
    participant MQ as FMC_MultiCamera.multi_cam_tuple_queue()
    participant SM as FMC_MultiCamera.show_multi_cam_opecv()
    Note over M: pathos_mp_helper.freeze_support()

    M->>+I:multi_cam=FMC_MultiCamera()
    I->>-M:return multi_cam
    activate M
    
    M->>+S:multi_cam.start(standalone_mode=True)
    deactivate M
    activate S
    rect rgb(10,150,150,.5)  
    alt if self.cams_to_use_list is None

        S->>+F:Find Available Cameras
        deactivate S
        F->>+S: return(cams_to_use_list)
        deactivate F
        end
        end
        S->>-P: self.start_multi_cam_process_pool
        activate P
        Note over P:CREATE cam_frame_q, multi_frame_tuple_queue, barrier(num_cams+1), exit_event
        Note over P:Write </br>'starting multi_cam_process_pool' to console
        rect rgb(150,150,150,.5)   
        loop with pathos_mp.ProcessingPool as self.cam_process_pool
            
            par MULTIPROCESS Camera0 
              rect rgb(150,10,15,.5)  
                P->>CI:initiate camera as subprocess
                Note over CI: if init received a 'queue' object, launch 'self.run_in_thread'
                CI->>CT:run cam in 'thread' mode
                P->>CI:initiate camera as subprocess
                CI->>CT:run cam in 'thread' mode 
                loop while: not exit_event.is_set()
                    CT->>CR:self.read_next_frame
                    CR->>CT:return(success, image, timestamp)
                    Note over CR: CREATE tuple(cam_num,image,timestamp) into self._frame_queue
                    CR->>+FQ:frame_tuple into frame_queue
                    Note over CR: Barrier.wait() (will release after frame_grabber grabs tuple)                                       
                end
            end
            and MULTIPROCESS Camera1 
              rect rgb(10,150,15,.5)  
                P->>CI:initiate camera as subprocess
                Note over CI: if init received a 'queue' object, launch 'self.run_in_thread'
                CI->>CT:run cam in 'thread' mode
                P->>CI:initiate camera as subprocess
                CI->>CT:run cam in 'thread' mode 
                loop while: not exit_event.is_set()
                    CT->>CR:self.read_next_frame
                    CR->>CT:return(success, image, timestamp)
                    Note over CR: CREATE tuple(cam_num,image,timestamp) into self._frame_queue
                    CR->>FQ:frame_tuple into frame_queue
                    Note over CR: Barrier.wait() (will release after frame_grabber grabs tuple)                                       
                end
            end
            and MULTIPROCESS CameraN 
              rect rgb(10,15,150,.5)  
                P->>CI:initiate camera as subprocess
                Note over CI: if init received a 'queue' object, launch 'self.run_in_thread'
                CI->>CT:run cam in 'thread' mode
                P->>CI:initiate camera as subprocess
                CI->>CT:run cam in 'thread' mode 
                loop while: not exit_event.is_set()
                    CT->>CR:self.read_next_frame
                    CR->>CT:return(success, image, timestamp)
                    Note over CR: CREATE tuple(cam_num,image,timestamp) into self._frame_queue
                    CR->>FQ:frame_tuple into frame_queue
                    Note over CR: Barrier.wait() (will release after frame_grabber grabs tuple)                                       
                end
            end

            and THREAD Incoming_frame_grabber
                rect rgb(150,180,15,.5)  

                loop exit_event is not set
                    FQ->>FG:grab frame_tuples
                    deactivate FQ
                    Note over FG: Release Barrier.wait()                    
                    Note over FG: CREATE multi_cam_tuple
                    FG->>+MQ:multi_cam_tuple into multi_cam_tuple_queue
                end
                end
            and show_stream_opencv
                rect rgb(210,25,210,.5)  

            alt if show_stream or standalont
                P->>SM:start multi cam stream
                MQ->>-SM: Grab frame
                Note over SM: Also stitch multi frame, and init out vid
            end
            end
            end     
        end                   
    end
```


```mermaid
classDiagram
    class FMC_MultiCamera{
        self,
        +[str] rec_name = None,
        +[pathlib.Path] save_path = None,
        [int] num_cams = 0,
        [list~int~]cams_to_use_list = None,
        [list~str~]rotation_codes_list = None,
        [bool] show_multi_cam_stream = True,
        [bool] save_to_mp4 = True,
        [bool] save_to_h5 = False,
        [bool] save_log_file = False 
        __init__()
        start(self, standalone_mode=False)
        find_available_cameras(self)
        start_multi_cam_process_pool(self)
        grab_incoming_cam_tuples(self)
        stitch_multicam_image(self, multi_cam_tuple)
        show_multi_cam_opencv(self)
        initialize_video(self, multi_cam_image)
        create_diagnostic_images(self)
        __enter__()
        __exit__()
    }
    
```