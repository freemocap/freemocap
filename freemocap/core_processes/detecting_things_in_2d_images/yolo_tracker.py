# -*- coding: utf-8 -*-
"""
Created on Thu Mar  9 18:19:00 2023

@author: karl
"""

from ultralytics import YOLO as _YOLO
import numpy as np
import cv2
import mediapipe as mp

mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


class YoloTracker:
    def __init__(self, mediapipe_tracker = None):
        
        self.model = _YOLO("yolov8n.pt")
        self.mp_tracker = mediapipe_tracker
        
    def detect(self, img):
                
        results = self.model.predict(source=img.copy(), save=False, save_txt=False)
        result = results[0]
        
        bboxes = np.array(result.boxes.xyxy.cpu(), dtype='int')
        
        class_ids = np.array(result.boxes.cls.cpu(), dtype="int")
        
        scores = np.array(result.boxes.conf.cpu(), dtype="float").round(2)
        
        return bboxes, class_ids, scores
    
    def cropped(self, img):
        
        bboxes, class_ids, _ = self.detect(img)
        
        if len(bboxes)!=1 and class_ids[0]!=0:
            print('YOLO did not find a person')
            return img, 0, 0
        
        box = bboxes[0]
        
        top_left_x, top_left_y, bottom_right_x, bottom_right_y = box
        
        img_cropped = img[top_left_y:bottom_right_y+1, top_left_x:bottom_right_x+1,:]
        
        return img_cropped, top_left_x, top_left_y
    
    
    def process_image(self, image=None):
        
        orig_height, orig_width, _ = image.shape
        
        cropped_img, top_left_x, top_left_y = self.cropped(image)
        
        crop_height, crop_width, _ = cropped_img.shape
        
        img_in = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB)
        
        results = self.mp_tracker.process(img_in)
    
    
        # modify results here
        for attr in ['pose_landmarks', 'face_landmarks', 'left_hand_landmarks', 'right_hand_landmarks']:
            
            mp_landmarks = getattr(results, attr)
            if mp_landmarks:
                for landmark in mp_landmarks.landmark:
                    landmark.x = (landmark.x*crop_width + top_left_x)/orig_width
                    landmark.y = (landmark.y*crop_height + top_left_y)/orig_height
                
        annotated_image = image.copy()
   
        # Draw pose, left and right hands, and face landmarks on the image.
        mp_drawing.draw_landmarks(
            annotated_image,
            results.face_landmarks,
            mp_holistic.FACEMESH_TESSELATION,
            landmark_drawing_spec=None,
            connection_drawing_spec=mp_drawing_styles
            .get_default_face_mesh_tesselation_style())
        mp_drawing.draw_landmarks(
            annotated_image,
            results.pose_landmarks,
            mp_holistic.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.
            get_default_pose_landmarks_style())
        
        return results, annotated_image
        
