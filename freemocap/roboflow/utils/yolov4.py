from freemocap.roboflow.tool.utils import *
from freemocap.roboflow.tool.torch_utils import *
from freemocap.roboflow.tool.darknet2pytorch import Darknet
from freemocap.roboflow.utils.general import non_max_suppression, xyxy2xywh
import cv2
import torch

class Yolov4Engine:
    def __init__(self, weights, cfgfile, device, names, classes, conf_thres, iou_thres, agnostic_nms, augment, half):
        self.model = Darknet(cfgfile)
        self.model.load_weights(weights[0])
        self.device = device

        if self.device != "cpu":
            self.model.cuda()

        self.classes = classes
        self.names = load_class_names(names)
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.augment = augment
        self.agnostic_nms = agnostic_nms

    def infer(self, img):
        img_resized = cv2.resize(img, (self.model.width, self.model.height))
        pred = do_detect(self.model, img_resized, self.conf_thres, self.iou_thres, self.device != "cpu")[0]
        return np.array(pred)

    def postprocess(self, pred, img_shape):
        height = img_shape[0]
        width = img_shape[1]
        classes = pred[:, 6].tolist()
        for i, cls in enumerate(classes):
            classes[i] = self.names[int(cls)]

        dets = pred[:, :5]
        for i, det in enumerate(dets):
            box = det
            x1 = int(box[0] * width)
            y1 = int(box[1] * height)
            x2 = int(box[2] * width)
            y2 = int(box[3] * height)
            newDet = [x1,y2-(y2-y1),x2-x1,y2-y1,det[4]]
            dets[i] = newDet
        return pred, classes


    def nms(self, pred):
        out = non_max_suppression(pred, self.conf_thres, self.iou_thres, classes=self.classes, agnostic=self.agnostic_nms)
        return out