# -*- coding: utf-8 -*-
'''

'''
import torch
import os, sys
from torch.nn import functional as F

import numpy as np
from packaging import version


__all__ = [
    "bboxes_iou",
    "bboxes_giou",
    "bboxes_diou",
    "bboxes_ciou",
]


if version.parse(torch.__version__) >= version.parse('1.5.0'):
    def _true_divide(dividend, divisor):
        return torch.true_divide(dividend, divisor)
else:
    def _true_divide(dividend, divisor):
        return dividend / divisor

def bboxes_iou(bboxes_a, bboxes_b, fmt='voc', iou_type='iou'):
    """Calculate the Intersection of Unions (IoUs) between bounding boxes.
    IoU is calculated as a ratio of area of the intersection
    and area of the union.

    Args:
        bbox_a (array): An array whose shape is :math:`(N, 4)`.
            :math:`N` is the number of bounding boxes.
            The dtype should be :obj:`numpy.float32`.
        bbox_b (array): An array similar to :obj:`bbox_a`,
            whose shape is :math:`(K, 4)`.
            The dtype should be :obj:`numpy.float32`.
    Returns:
        array:
        An array whose shape is :math:`(N, K)`. \
        An element at index :math:`(n, k)` contains IoUs between \
        :math:`n` th bounding box in :obj:`bbox_a` and :math:`k` th bounding \
        box in :obj:`bbox_b`.

    from: https://github.com/chainer/chainercv
    """
    if bboxes_a.shape[1] != 4 or bboxes_b.shape[1] != 4:
        raise IndexError

    N, K = bboxes_a.shape[0], bboxes_b.shape[0]

    if fmt.lower() == 'voc':  # xmin, ymin, xmax, ymax
        # top left
        tl_intersect = torch.max(
            bboxes_a[:, np.newaxis, :2],
            bboxes_b[:, :2]
        ) # of shape `(N,K,2)`
        # bottom right
        br_intersect = torch.min(
            bboxes_a[:, np.newaxis, 2:],
            bboxes_b[:, 2:]
        )
        bb_a = bboxes_a[:, 2:] - bboxes_a[:, :2]
        bb_b = bboxes_b[:, 2:] - bboxes_b[:, :2]
        # bb_* can also be seen vectors representing box_width, box_height
    elif fmt.lower() == 'yolo':  # xcen, ycen, w, h
        # top left
        tl_intersect = torch.max(
            bboxes_a[:, np.newaxis, :2] - bboxes_a[:, np.newaxis, 2:] / 2,
            bboxes_b[:, :2] - bboxes_b[:, 2:] / 2
        )
        # bottom right
        br_intersect = torch.min(
            bboxes_a[:, np.newaxis, :2] + bboxes_a[:, np.newaxis, 2:] / 2,
            bboxes_b[:, :2] + bboxes_b[:, 2:] / 2
        )
        bb_a = bboxes_a[:, 2:]
        bb_b = bboxes_b[:, 2:]
    elif fmt.lower() == 'coco':  # xmin, ymin, w, h
        # top left
        tl_intersect = torch.max(
            bboxes_a[:, np.newaxis, :2],
            bboxes_b[:, :2]
        )
        # bottom right
        br_intersect = torch.min(
            bboxes_a[:, np.newaxis, :2] + bboxes_a[:, np.newaxis, 2:],
            bboxes_b[:, :2] + bboxes_b[:, 2:]
        )
        bb_a = bboxes_a[:, 2:]
        bb_b = bboxes_b[:, 2:]
    
    area_a = torch.prod(bb_a, 1)
    area_b = torch.prod(bb_b, 1)
    
    # torch.prod(input, dim, keepdim=False, dtype=None) → Tensor
    # Returns the product of each row of the input tensor in the given dimension dim
    # if tl, br does not form a nondegenerate squre, then the corr. element in the `prod` would be 0
    en = (tl_intersect < br_intersect).type(tl_intersect.type()).prod(dim=2)  # shape `(N,K,2)` ---> shape `(N,K)`

    area_intersect = torch.prod(br_intersect - tl_intersect, 2) * en  # * ((tl < br).all())
    area_union = (area_a[:, np.newaxis] + area_b - area_intersect)

    iou = _true_divide(area_intersect, area_union)

    if iou_type.lower() == 'iou':
        return iou

    if fmt.lower() == 'voc':  # xmin, ymin, xmax, ymax
        # top left
        tl_union = torch.min(
            bboxes_a[:, np.newaxis, :2],
            bboxes_b[:, :2]
        ) # of shape `(N,K,2)`
        # bottom right
        br_union = torch.max(
            bboxes_a[:, np.newaxis, 2:],
            bboxes_b[:, 2:]
        )
    elif fmt.lower() == 'yolo':  # xcen, ycen, w, h
        # top left
        tl_union = torch.min(
            bboxes_a[:, np.newaxis, :2] - bboxes_a[:, np.newaxis, 2:] / 2,
            bboxes_b[:, :2] - bboxes_b[:, 2:] / 2
        )
        # bottom right
        br_union = torch.max(
            bboxes_a[:, np.newaxis, :2] + bboxes_a[:, np.newaxis, 2:] / 2,
            bboxes_b[:, :2] + bboxes_b[:, 2:] / 2
        )
    elif fmt.lower() == 'coco':  # xmin, ymin, w, h
        # top left
        tl_union = torch.min(
            bboxes_a[:, np.newaxis, :2],
            bboxes_b[:, :2]
        )
        # bottom right
        br_union = torch.max(
            bboxes_a[:, np.newaxis, :2] + bboxes_a[:, np.newaxis, 2:],
            bboxes_b[:, :2] + bboxes_b[:, 2:]
        )
    
    # c for covering, of shape `(N,K,2)`
    # the last dim is box width, box hight
    bboxes_c = br_union - tl_union

    area_covering = torch.prod(bboxes_c, 2)  # shape `(N,K)`

    giou = iou - _true_divide(area_covering - area_union, area_covering)

    if iou_type.lower() == 'giou':
        return giou

    if fmt.lower() == 'voc':  # xmin, ymin, xmax, ymax
        centre_a = (bboxes_a[..., 2 :] + bboxes_a[..., : 2]) / 2
        centre_b = (bboxes_b[..., 2 :] + bboxes_b[..., : 2]) / 2
    elif fmt.lower() == 'yolo':  # xcen, ycen, w, h
        centre_a = bboxes_a[..., : 2]
        centre_b = bboxes_b[..., : 2]
    elif fmt.lower() == 'coco':  # xmin, ymin, w, h
        centre_a = bboxes_a[..., 2 :] + bboxes_a[..., : 2]/2
        centre_b = bboxes_b[..., 2 :] + bboxes_b[..., : 2]/2

    centre_dist = torch.norm(centre_a[:, np.newaxis] - centre_b, p='fro', dim=2)
    diag_len = torch.norm(bboxes_c, p='fro', dim=2)

    diou = iou - _true_divide(centre_dist.pow(2), diag_len.pow(2))

    if iou_type.lower() == 'diou':
        return diou

    """ the legacy custom cosine similarity:

    # bb_a of shape `(N,2)`, bb_b of shape `(K,2)`
    v = torch.einsum('nm,km->nk', bb_a, bb_b)
    v = _true_divide(v, (torch.norm(bb_a, p='fro', dim=1)[:,np.newaxis] * torch.norm(bb_b, p='fro', dim=1)))
    # avoid nan for torch.acos near \pm 1
    # https://github.com/pytorch/pytorch/issues/8069
    eps = 1e-7
    v = torch.clamp(v, -1+eps, 1-eps)
    """
    v = F.cosine_similarity(bb_a[:,np.newaxis,:], bb_b, dim=-1)
    v = (_true_divide(2*torch.acos(v), np.pi)).pow(2)
    with torch.no_grad():
        alpha = (_true_divide(v, 1-iou+v)) * ((iou>=0.5).type(iou.type()))

    ciou = diou - alpha * v

    if iou_type.lower() == 'ciou':
        return ciou


def bboxes_giou(bboxes_a, bboxes_b, fmt='voc'):
    return bboxes_iou(bboxes_a, bboxes_b, fmt, 'giou')


def bboxes_diou(bboxes_a, bboxes_b, fmt='voc'):
    return bboxes_iou(bboxes_a, bboxes_b, fmt, 'diou')


def bboxes_ciou(bboxes_a, bboxes_b, fmt='voc'):
    return bboxes_iou(bboxes_a, bboxes_b, fmt, 'ciou')
