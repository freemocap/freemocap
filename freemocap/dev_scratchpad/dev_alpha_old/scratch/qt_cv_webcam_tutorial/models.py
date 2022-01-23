# from - https://www.pythonforthelab.com/blog/step-by-step-guide-to-building-a-gui/

import cv2 

class Camera: 
    def __init__(self, cam_num):
        self.cap = None
        self.cam_num = cam_num

    def initialize(self):
        self.cap = cv2.VideoCapture(self.cam_num, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) 

    def get_frame(self):
        success_bool, self.last_frame = self.cap.read()
        return self.last_frame

    def acquire_movie(self, num_frames):
        movie = []
        for _ in range(num_frames):
            movie.append(self.get_frame())
        
        return movie

    def set_brightness(self, value):
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, value)

    def get_brightness(self):
        return self.cap.get(cv2.CAP_PROP_BRIGHTNESS)
        
    def __str__(self):
        return 'OpenCV Camera {}'.format(self.cam_num)
    
    def close_camera(self):
        self.cap.release()

if __name__ == '__main__':
    cam = Camera(0)
    cam.initialize()
    print(cam)
    cam.close_camera()