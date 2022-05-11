import requests
import base64
import io
import cv2
from PIL import Image
import numpy as np


def predict_image(image, api_key, url, confidence, overlap, idx):
    retval, buffer = cv2.imencode('.jpg', image)
    img_str = base64.b64encode(buffer)
    img_str = img_str.decode("ascii")

    # Construct the URL
    upload_url = "".join([
        url,
        "?api_key=",
        api_key,
        "&confidence=",
        str(confidence),
        "&overlap=",
        str(overlap),
        "&name=",
        str(idx),
        ".jpg"
    ])

    # POST to the API
    r = requests.post(upload_url, data=img_str, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    })

    json = r.json()

    predictions = json["predictions"]
    formatted_predictions = []
    classes = []

    for pred in predictions:
        formatted_pred = [pred["x"], pred["y"], pred["width"], pred["height"], pred["confidence"]]

        # convert to top-left x/y from center
        formatted_pred[0] -= formatted_pred[2]/2
        formatted_pred[1] -= formatted_pred[3]/2

        formatted_predictions.append(formatted_pred)
        classes.append(pred["class"])

    #print(formatted_predictions)

    return formatted_predictions, classes