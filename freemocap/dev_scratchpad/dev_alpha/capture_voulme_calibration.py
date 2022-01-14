from rich.console import Console
from FMC_MultiCamera import FMC_MultiCamera
import socket
from pathlib import Path
from pathos.helpers import mp as pathos_mp_helper
import cv2

aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_6X6_250)
board = cv2.aruco.CharucoBoard_create(7, 5, 1, .8, aruco_dict)

def detect_charuco_board(image):
    """
    Charuco base pose estimation.
    more-or-less copied from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco/sandbox/ludovic/aruco_calibration_rotation.html
    """
    allCorners = []
    allIds = []
    # SUB PIXEL CORNER DETECTION CRITERION
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.00001)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    charuco_corners, charuco_corner_ids, rejectedImgPoints = cv2.aruco.detectMarkers(gray, aruco_dict)
    
    if len(charuco_corners)>0:
        # SUB PIXEL DETECTION
        for this_corner in charuco_corners:
            cv2.cornerSubPix(gray, this_corner,
                                winSize = (3,3),
                                zeroZone = (-1,-1),
                                criteria = criteria)
        res2 = cv2.aruco.interpolateCornersCharuco(charuco_corners,charuco_corner_ids,gray,board)


    return charuco_corners,charuco_corner_ids


if __name__ == "__main__":
    pathos_mp_helper.freeze_support()

    console = Console() #create rich console to catch and print exceptions


    this_computer_name = socket.gethostname()

    freemocap_data_path=None
    in_rotation_codes_list=None
        
    if this_computer_name=='jon-hallway-XPS-8930':
        freemocap_data_path = Path('/home/jon/Dropbox/FreeMoCapProject/FreeMocap_Data')
        in_rotation_codes_list = ['cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', ]
    elif this_computer_name == 'DESKTOP-DCG6K4F':
        freemocap_data_path = Path(r'C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data')
    elif this_computer_name == 'Jons-MacBook-Pro.local':
        freemocap_data_path = Path('/Users/jon/Dropbox/FreeMoCapProject')

    try:
        multi_cam = FMC_MultiCamera(show_multi_cam_stream_bool = False, freemocap_data_folder=str(freemocap_data_path), rotation_codes_list=in_rotation_codes_list)
        multi_cam.start()        



        
        console.rule('Launching Multi Cam Viewer')
        frame_count = 0
        while not multi_cam.exit_event.is_set():   
            if not multi_cam.multi_cam_tuple_queue.empty():
                
                this_multi_cam_tuple = multi_cam.multi_cam_tuple_queue.get()
                frame_count += 1
                
                multi_cam.save_synchronized_videos(this_multi_cam_tuple)
                
                if frame_count % 30 == 0:
                    for this_cam_idx in range(multi_cam.num_cams):
                        this_cam_tuple = this_multi_cam_tuple[this_cam_idx]
                        this_cam_image = this_cam_tuple[1]
                        charuco_corners,charuco_corner_ids = detect_charuco_board(this_cam_image)
                        f=9
                    
                    
                this_multi_cam_image = multi_cam.stitch_multicam_image(this_multi_cam_tuple)

                if multi_cam._save_multi_cam_to_mp4:
                    if multi_cam._output_multi_cam_video_object is None:
                        multi_cam.initialize_multi_cam_output_video(this_multi_cam_image)
                    

                    multi_cam._output_multi_cam_video_object.write(this_multi_cam_image)
                
                if multi_cam._save_each_cam_to_mp4:
                    if multi_cam._each_cam_video_writer_object_list is None:
                        multi_cam.initialize_each_cam_output_video(this_multi_cam_tuple)
                    
                    for this_cam_num in range(multi_cam.num_cams):
                        multi_cam._each_cam_video_writer_object_list[this_cam_num].write(this_multi_cam_tuple[this_cam_num][1])

                cv2.imshow(multi_cam._rec_name, this_multi_cam_image)
                key = cv2.waitKey(1)

                if key == 27:  # exit on ESC                        
                    break
                
                if cv2.getWindowProperty(multi_cam._rec_name, cv2.WND_PROP_VISIBLE) < 1: #break loop if window closed
                    break

        cv2.destroyAllWindows()
        
        if multi_cam._save_multi_cam_to_mp4:
            multi_cam._output_multi_cam_video_object.release()
            
        if multi_cam._save_each_cam_to_mp4:
            for this_cam_num in range(multi_cam.num_cams):
                multi_cam._each_cam_video_writer_object_list[this_cam_num].release()

        console.rule('Shutting down MultiCamera Viewer')
        multi_cam.exit_event.set() #send the 'Exit' signal to everyone.
    
                                            
    except Exception:
        console.print_exception()
