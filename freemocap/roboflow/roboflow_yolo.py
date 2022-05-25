import argparse
import time
from pathlib import Path
import os
from tkinter import font

import freemocap.roboflow.clip as clip
import mediapipe as mp
import cv2
import torch
import torch.backends.cudnn as cudnn
from numpy import random
import numpy as np
import pandas as pd

from freemocap.roboflow.models.experimental import attempt_load
from freemocap.roboflow.utils.datasets import LoadStreams, LoadImages
from freemocap.roboflow.utils.general import xyxy2xywh, xywh2xyxy, \
    strip_optimizer, set_logging, increment_path, scale_coords
from freemocap.roboflow.utils.plots import plot_one_box
from freemocap.roboflow.utils.torch_utils import select_device, time_sync
from freemocap.roboflow.utils.roboflow import predict_image

# deep sort imports
from freemocap.roboflow.deep_sort import preprocessing, nn_matching
from freemocap.roboflow.deep_sort.detection import Detection
from freemocap.roboflow.deep_sort.tracker import Tracker
from freemocap.roboflow.tools import generate_clip_detections as gdet

from freemocap.roboflow.utils.yolov5 import Yolov5Engine
from freemocap.roboflow.utils.yolov4 import Yolov4Engine






def write_bbox_over_image(tracker,save_path,im0, info,detection_engine,thickness,names):
    #Taxes the bounding box coords and plots the box over the image
    if len(tracker.tracks):
        print("[Tracks]", len(tracker.tracks))

    for track in tracker.tracks:
        
        if not track.is_confirmed() or track.time_since_update > 1:
            continue
        xyxy = track.to_tlbr()
        class_num = track.class_num
        bbox = xyxy
        class_name = names[int(class_num)] if detection_engine == "yolov5" else class_num
        if info:
            print("Tracker ID: {}, Class: {}, BBox Coords (xmin, ymin, xmax, ymax): {}".format(
                str(track.track_id), class_name, (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))))

        label = f'{class_name} #{track.track_id}'
        plot_one_box(xyxy, im0,save_path=save_path, label=label,
                        color=get_color_for(label), line_thickness=thickness)
        

def get_color_for(class_num):
    #Bounding box label color
    colors = [
        "#4892EA",
        "#00EEC3",
        "#FE4EF0",
        "#F4004E",
        "#FA7200",
        "#EEEE17",
        "#90FF00",
        "#78C1D2",
        "#8C29FF"
    ]

    num = hash(class_num) # may actually be a number or a string
    hex = colors[num%len(colors)]
    # adapted from https://stackoverflow.com/questions/29643352/converting-hex-to-rgb-value-in-python
    rgb = tuple(int(hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    return rgb


def run_roboflow(weights='yolov5s.pt',
           cfg = 'yolov5.cfg0',
           names = 'coco.names',
           input_video = 'data/images',
           img_size = 640,
           confidence=0.4,
           overlap=0.3,
           thickness=3,
           device ='',
           view_img = False,
           save_txt = True,
           save_conf = True,
           classes =0,
           agnostic_nms = True,
           augment = True,
           update = True,
           project = 'runs/detect',
           name = 'exp',
           exist_ok = True,
           nms_max_overlap=1.0, 
           max_cosine_distance = .4,
           nn_budget = None,
           api_key = None,
           info = True,
           url = None,
           detection_engine = 'yolov5',
           save_bbox_vid=True):

    """Function takes an input video, runs through yolo and deep sort algorithms to 
    output a dictionary with the coordinates of a bounding box over each person in the 
    vide"""

    t0 = time_sync()
    # initialize deep sort
    model_filename = "ViT-B/16"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    half = device != "cpu"
    model, transform = clip.load(model_filename, device=device, jit=False)
    model.eval()
    encoder = gdet.create_box_encoder(model, transform, batch_size=1, device=device)
    # calculate cosine distance metric
    metric = nn_matching.NearestNeighborDistanceMetric(
        "cosine", max_cosine_distance, nn_budget)

    # load yolov5 model here
    if detection_engine == "yolov5":
        yolov5_engine = Yolov5Engine(weights, device, classes, confidence, overlap, agnostic_nms, augment, half)
        names = yolov5_engine.get_names()

    elif detection_engine == "yolov4":
        yolov4_engine = Yolov4Engine(weights, cfg, device, names, classes, confidence, overlap, agnostic_nms, augment, half)

    # initialize tracker
    tracker = Tracker(metric)
    source, weights, view_img, save_txt, imgsz = input_video, weights, view_img, save_txt, img_size
    webcam = source.isnumeric() or source.endswith('.txt') or source.lower().startswith(
        ('rtsp://', 'rtmp://', 'http://'))

    # Initialize
    set_logging()
    device = select_device(device)
    half = device.type != 'cpu'  # half precision only supported on CUDA

    # Set Dataloader
    vid_path, vid_writer = None, None
    if webcam:
        view_img = True
        cudnn.benchmark = True  # set True to speed up constant image size inference
        dataset = LoadStreams(source, img_size=imgsz)
    else:
        save_img = True
        dataset = LoadImages(source, img_size=imgsz)

    frame_count = 0
    dict_of_all_tracks = {}
    img = torch.zeros((1, 3, imgsz, imgsz), device=device)  # init img
    if detection_engine == "yolov5":
        _ = yolov5_engine.infer(img.half() if half else img) if device.type != 'cpu' else None  # run once
    for path,im0,im0s,vid_cap,test5 in dataset:
        
        img = torch.from_numpy(im0).to(device)
        img = img.half() if half else img.float()  # uint8 to fp16/32
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        # Roboflow Inference
        t1 = time_sync()
        p, s, im0, frame = path, '', im0s, getattr(dataset, 'frame', 0)
        if frame%100 == 0:
            print('YOLO on Frame '+str(frame))
        # choose between prediction engines (yolov5 and roboflow)
        if detection_engine == "roboflow":
            pred, classes = predict_image(im0, api_key, url, confidence, overlap, frame_count)
            pred = [torch.tensor(pred)]
        elif detection_engine == "yolov5":
            # print("yolov5 inference")
            pred = yolov5_engine.infer(img)
        else:
            # print("yolov4 inference {}".format(im0.shape))
            pred = yolov4_engine.infer(im0)
            pred, classes = yolov4_engine.postprocess(pred, im0.shape)
            pred = [torch.tensor(pred)]

        t2 = time_sync()

        
        # Process detections
        for i, det in enumerate(pred):  # detections per image
            #moved up to roboflow inference
            """if webcam:  # batch_size >= 1
                p, s, im0, frame = path[i], '%g: ' % i, im0s[i].copy(
                ), dataset.count
            else:
                p, s, im0, frame = path, '', im0s, getattr(dataset, 'frame', 0)"""

            p = Path(p)  # to Path

            # normalization gain whwh
            gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]
            if len(det):

                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()
                for c in det[:, -1].unique():
                    n = (det[:, -1] == c).sum()  # detections per class
                    s += f'{n} {names[int(c)]}s, '  # add to string

                # Transform bboxes from tlbr to tlwh
                trans_bboxes = det[:, :4].clone()
                trans_bboxes[:, 2:] -= trans_bboxes[:, :2]
                bboxes = trans_bboxes[:, :4].cpu()
                confs = det[:, 4]
                class_nums = det[:, -1]
                classes = class_nums
      
                # encode yolo detections and feed to tracker
                features = encoder(im0, bboxes)
                detections = [Detection(bbox, conf, class_num, feature) for bbox, conf, class_num, feature in zip(
                    bboxes, confs, classes, features)]

                # run non-maxima supression
                boxs = np.array([d.tlwh for d in detections])
                scores = np.array([d.confidence for d in detections])
                class_nums = np.array([d.class_num.cpu() for d in detections])
                indices = preprocessing.non_max_suppression(
                    boxs, class_nums, nms_max_overlap, scores)
                detections = [detections[i] for i in indices]

                # Call the tracker
                tracker.predict()
                tracker.update(detections)
                
                #Loop through each tracked person and save their coords to a dataframe with their ID
                for track in tracker.tracks:
                    if track.track_id in dict_of_all_tracks.keys():
                        xyxy = np.array(track.to_tlbr())
                        fr_xyxy = np.insert(xyxy,0,frame)
                        this_frame_df = pd.DataFrame(fr_xyxy).T
                        this_frame_df.columns = ['frame','Xmin','Ymin','Xmax','Ymax']
                        current_df_for_this_track =dict_of_all_tracks[track.track_id]
                        
                        appended_df = current_df_for_this_track.append(this_frame_df)
                        dict_of_all_tracks[track.track_id] = appended_df
                    else:
                        xyxy = np.array(track.to_tlbr())
                        fr_xyxy = np.insert(xyxy,0,frame)
                        
                        this_frame_df = pd.DataFrame(fr_xyxy).T
                        this_frame_df.columns = ['frame','Xmin','Ymin','Xmax','Ymax']
                        
                        dict_of_all_tracks[track.track_id] = this_frame_df        

    print(f'Done. ({time.time() - t0:.3f}s)')

    return dict_of_all_tracks