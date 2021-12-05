##
##
##  ███████ ███    ███  ██████     ███████ ███████ ███████ ███████ ██  ██████  ███    ██ 
##  ██      ████  ████ ██          ██      ██      ██      ██      ██ ██    ██ ████   ██ 
##  █████   ██ ████ ██ ██          ███████ █████   ███████ ███████ ██ ██    ██ ██ ██  ██ 
##  ██      ██  ██  ██ ██               ██ ██           ██      ██ ██ ██    ██ ██  ██ ██ 
##  ██      ██      ██  ██████     ███████ ███████ ███████ ███████ ██  ██████  ██   ████ 
##                                                                                       
## https://patorjk.com/software/taag/#p=display&f=ANSI%20Regular&t=FMC%20Session

from FMC_MultiCamera import FMC_MultiCamera
import datetime
from pathlib import Path
import pickle 

from rich import print, inspect
from rich.console import Console
import numpy as np 

from freemocap import fmc_anipose
from aniposelib.boards import CharucoBoard

rich_console = Console()


class FMC_Session:
    ## 
    ## 
    ##                 ██ ███    ██ ██ ████████                 
    ##                 ██ ████   ██ ██    ██                    
    ##                 ██ ██ ██  ██ ██    ██                    
    ##                 ██ ██  ██ ██ ██    ██                    
    ## ███████ ███████ ██ ██   ████ ██    ██    ███████ ███████ 
    ##                                                          
    ## 

    def __init_(self):
        
        self.sessionID = datetime.datetime.now().strftime("FreeMoCap_Session_%Y-%b-%d_%H_%M_%S")
        self.save_path = Path('data/' + self._rec_name)
        self.save_path.mkdir(parents=True)
        self.path_to_log_file = Path(str(self.save_path / self.sessionID) + '_log.txt')
    
    ##   
    ##   ██████  ███████  ██████     ███    ███ ██    ██ ██      ████████ ██      ██████  █████  ███    ███ 
    ##   ██   ██ ██      ██          ████  ████ ██    ██ ██         ██    ██     ██      ██   ██ ████  ████ 
    ##   ██████  █████   ██          ██ ████ ██ ██    ██ ██         ██    ██     ██      ███████ ██ ████ ██ 
    ##   ██   ██ ██      ██          ██  ██  ██ ██    ██ ██         ██    ██     ██      ██   ██ ██  ██  ██ 
    ##   ██   ██ ███████  ██████     ██      ██  ██████  ███████    ██    ██      ██████ ██   ██ ██      ██ 
    ##                                                                                                      
    ##                                                                                                      
            
    def record_multi_cam(self,save_path=None, rotation_codes_list=None):
        self.multi_cam = FMC_MultiCamera(save_path=str(freemocap_data_path), rotation_codes_list=in_rotation_codes_list )
        self.multi_cam.start()    
    
    ##          
    ##          
    ##   ██████  █████  ██      ██ ██████       ██████  █████  ██████      ██    ██  ██████  ██      
    ##  ██      ██   ██ ██      ██ ██   ██     ██      ██   ██ ██   ██     ██    ██ ██    ██ ██      
    ##  ██      ███████ ██      ██ ██████      ██      ███████ ██████      ██    ██ ██    ██ ██      
    ##  ██      ██   ██ ██      ██ ██   ██     ██      ██   ██ ██           ██  ██  ██    ██ ██      
    ##   ██████ ██   ██ ███████ ██ ██████       ██████ ██   ██ ██            ████    ██████  ███████ 
    ##                                                                                               
    ##  
    
    def calibrate_capture_volume(self, charucoSquareSize=36):
        
        num_charuco_rows = 7
        num_charuco_cols = 5
        num_charuco_tracked_points = (num_charuco_rows-1) * (num_charuco_cols-1)
        board = CharucoBoard(num_charuco_rows, num_charuco_cols,
                    #square_length=1, # here, in mm but any unit works (JSM NOTE - just using '1' so resulting units will be in 'charuco squarelenghts`)
                    #marker_length=.8,
                    #  square_length = 121, #big boi charuco
                    #  marker_length = 98,
                    square_length = charucoSquareSize,#mm
                    marker_length = charucoSquareSize*.8,#mm
                    marker_bits=4, dict_size=250)
        
        
        
        video_paths_list = self.multi_cam._each_cam_video_filename_list
        
        video_paths_list_of_list_of_strings = []
        
        for this_path in video_paths_list:
            video_paths_list_of_list_of_strings.append([str(this_path)])#anipose needs this to be a list of lists (which is annoying by whatevs)

        cam_names = ['cam_'+str(cam_num) for cam_num in range(len(video_paths_list))]
        
        self.anipose_camera_calibration = fmc_anipose.CameraGroup.from_names(cam_names, fisheye=True  )  # Looking through their code... it looks lke the 'fisheye=True' doesn't do much (see 2020-03-29 obsidian note)    
        error,charuco_frame_data, charuco_frame_numbers = self.anipose_camera_calibration.calibrate_videos(video_paths_list_of_list_of_strings, board)   

        print("Anipose Calibration Successful!")

        #save calibration info to files 
        calibration_toml_filename = "{}_camera_calibration.toml".format(self.multi_cam._rec_name)        
        self.camera_calibration_toml_path = self.multi_cam._save_path / calibration_toml_filename        
        self.anipose_camera_calibration.dump(self.camera_calibration_toml_path) 

        camera_calibration_info_dict = self.anipose_camera_calibration.get_dicts()
        camera_calibration_pickle_path = self.multi_cam._save_path / "{}_camera_calibration.pickle".format(self.multi_cam._rec_name)

        with open(str(camera_calibration_pickle_path), 'wb') as pickle_file:
            pickle.dump(camera_calibration_info_dict, pickle_file)  
            
        #convert charuco data into a format that can be 3d reconstructed (effectively providing dummy data for the rest of the 3d reconstruction pipeline)
        self.charuco_nCams_nFrames_nImgPts_XY = np.empty([self.multi_cam.num_cams, self.multi_cam.num_frames, num_charuco_tracked_points,  2])
        self.charuco_nCams_nFrames_nImgPts_XY[:] = np.nan

        
        for this_charuco_frame_data, this_charuco_frame_num in zip(charuco_frame_data,charuco_frame_numbers):
            for this_cam_num in range(self.multi_cam.num_cams):
                try:
                    self.charuco_nCams_nFrames_nImgPts_XY[this_cam_num, this_charuco_frame_num, :,:] = np.squeeze(this_charuco_frame_data[this_cam_num]["filled"])
                except:
                    # print("failed frame:", frame)
                    continue
    ####            
    ####    
    ####    ██████  ███████  ██████  ██████  ███    ██ ███████ ████████ ██████  ██    ██  ██████ ████████     ██████  ██████  
    ####    ██   ██ ██      ██      ██    ██ ████   ██ ██         ██    ██   ██ ██    ██ ██         ██             ██ ██   ██ 
    ####    ██████  █████   ██      ██    ██ ██ ██  ██ ███████    ██    ██████  ██    ██ ██         ██         █████  ██   ██ 
    ####    ██   ██ ██      ██      ██    ██ ██  ██ ██      ██    ██    ██   ██ ██    ██ ██         ██             ██ ██   ██ 
    ####    ██   ██ ███████  ██████  ██████  ██   ████ ███████    ██    ██   ██  ██████   ██████    ██        ██████  ██████  
    ####                                                                                                                      
    ####                                                                                                                      

    def reconstruct3D(self, data_nCams_nFrames_nImgPts_XYC, calibration_toml_path = None, confidence_threshold=0):
                
        if calibration_toml_path: #if the user specified a calibration toml (from a previous Anipose-based calibration) - load it here. Otherwise, assume the calibration is included in `self`                        
            self.anipose_camera_calibration = fmc_anipose.CameraGroup.load(str(calibration_toml_path))

        num_cams, num_frames, num_img_points, num_dims = data_nCams_nFrames_nImgPts_XYC.shape

        if num_dims == 3: #if there are 3 dimensions, the third one is 'confidence' and can be used to threshold out low-confidence tracks
            dataOG = data_nCams_nFrames_nImgPts_XYC.copy()

            for camNum in range(num_cams):
                            
                thisCamX = data_nCams_nFrames_nImgPts_XYC[camNum, :, :,0 ]
                thisCamY = data_nCams_nFrames_nImgPts_XYC[camNum, :, :,1 ]
                thisCamConf = data_nCams_nFrames_nImgPts_XYC[camNum, :, :, 2]

                thisCamX[thisCamConf < confidence_threshold] = np.nan
                thisCamY[thisCamConf < confidence_threshold] = np.nan                                        


        if num_dims == 2:
            data_nCams_nFrames_nImgPts_XY = data_nCams_nFrames_nImgPts_XYC
        elif num_dims == 3:
            data_nCams_nFrames_nImgPts_XY = np.squeeze(data_nCams_nFrames_nImgPts_XYC[:, :, :, 0:2])

        dataFlat_nCams_nTotalPoints_XY = data_nCams_nFrames_nImgPts_XY.reshape(num_cams, -1, 2)  # reshape data to collapse across 'frames' so it becomes [numCams, numFrames*numPoints, XY]

        console.print('Reconstructing 3d points...')
        data3d_flat = self.anipose_camera_calibration.triangulate(dataFlat_nCams_nTotalPoints_XY, progress=True)

        dataReprojerr_flat = self.anipose_camera_calibration.reprojection_error( data3d_flat, dataFlat_nCams_nTotalPoints_XY, mean=True)

        ##return:
        data_fr_mar_xyz = data3d_flat.reshape(num_frames, num_img_points, 3)
        dataReprojErr = dataReprojerr_flat.reshape(num_frames, num_img_points)

        return data_fr_mar_xyz, dataReprojErr
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
        """Context manager -  no need to do anything special on stop (maybe set 'exit_event?" """
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

if __name__ == "__main__":
    
    import socket
    this_computer_name = socket.gethostname()
    
    console = Console()
    
    freemocap_data_path=None
    in_rotation_codes_list=None
    charucoSquareSize = 36
    
    if this_computer_name=='jon-hallway-XPS-8930':
        freemocap_data_path = Path('/home/jon/Dropbox/FreeMoCapProject/FreeMocap_Data')
        in_rotation_codes_list = ['cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', ]
    elif this_computer_name == 'DESKTOP-DCG6K4F':
        freemocap_data_path = Path(r'C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data')
        this_charucoSquareSize = 123
    
    try:
        sesh =  FMC_Session()
        sesh.record_multi_cam(save_path=str(freemocap_data_path), rotation_codes_list=in_rotation_codes_list)
        sesh.calibrate_capture_volume(charucoSquareSize = this_charucoSquareSize)
        sesh.charuco_nFrames_nTrackedPoints_XYZ, sesh.charuco_reprojection_error = sesh.reconstruct3D(sesh.charuco_nCams_nFrames_nImgPts_XY)
        f=9
        charuco3d_filename = sesh.multi_cam._save_path/'charuco_3d_points.npy'
        np.save(charuco3d_filename,sesh.charuco_nFrames_nTrackedPoints_XYZ)
    except:
        console.print_exception()