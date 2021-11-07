
____
 # FMC_Camera
>
>   A class to open and run a single webcam, either in 'standalone' mode, or as part of a MultiCam object
## Class definition and contents
```mermaid
classDiagram
    class FMC_Camera{
        +[int] cam_num = 0
        +[queue] frame_queue = None
        +[barrier] barrier = None
        +[event] exit_event = None
        +[bool] show_cam_stream = False
        +[rich_console] rich_console = None,       
        +[bool] show_console = False,       
        +[dict] cap_parameters_dict = cap_default_parameters_dict,
        +[bool] vid_save_path=None, 
        __init__()
        show_cam_stream(self, show_cam_stream_bool=True)
        open(self)
        show(self)
        run_in_thread(self)
        __enter__()
        __exit__()
    }
    
```
---
## Run as __Main__ file - Code sequence chart
```mermaid
%%{init: {"securityLevel": "loose","theme": "base", "themeVariables": { "primaryColor": "#fff4dd", "primaryBorderColor":"#Fffff0","primaryTextColor":"#FFF", "actorBkg":"#FF0000", "loopTextColor":"#fff000","activationBkgColor":"#000FFF", "sequenceNumberColor":"#000000"}}}%%
sequenceDiagram
autonumber
    participant M as __Main__
    participant I as FMC_Camera.__init__()
    participant S as cam.show()
    participant R as self.read_next_frame()

    activate M    
    loop Create FMC_Camera object 'cam' as context manager
        rect rgb(150,10,150,.5)   
        M->>+I:cam = FMC_Camera()
        deactivate M        
        Note over I: create "cam" with default values
        I->>-M:return "cam"
        activate M        
        M->>+S:Launch video stream window (OpenCV)
        deactivate M
        Note over S: Play Video Stream in floating window
        
        loop Display Video - cam.show()
            rect rgb(0,80,100,.8)
            S->>+R:self.read_next_frame()        
            deactivate S
            R->>R:read frame - self.cv2_cap.read()
            R->>R:record timestamp to self
            R->>-S:return (success, image, timestamp_unix_ns)
            activate S
            S->>S:Display image: cv2.imshow()
            S->>S:print "camName read an image at.." to console
            Note over S:EXIT on window close of ESC key
            end
            end
        S->>-M:break
        
        activate M
        deactivate M
        end
    end
```
