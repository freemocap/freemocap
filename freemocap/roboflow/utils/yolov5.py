from freemocap.roboflow.models.experimental import attempt_load
from freemocap.roboflow.utils.general import non_max_suppression

class Yolov5Engine:
    def __init__(self, weights, device, classes, conf_thres, iou_thres, agnostic_nms, augment, half):
        self.model = attempt_load(weights, map_location=device)
        if half:
            self.model.half()
        self.classes = classes
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.augment = augment
        self.agnostic_nms = agnostic_nms

    def infer(self, img):
        pred = self.model(img, augment=self.augment)[0]
        pred = self.nms(pred)
        return pred

    def nms(self, pred):
        out = non_max_suppression(pred, self.conf_thres, self.iou_thres, classes=self.classes, agnostic=self.agnostic_nms)
        return out

    def get_names(self):
        return self.model.module.names if hasattr(self.model, 'module') else self.model.names