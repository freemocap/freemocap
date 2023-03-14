import cv from "@techstark/opencv-js";

export class Capture {
  private FPS = 60;
  private _cap: cv.VideoCapture;
  private _ws: WebSocket;

  constructor(videoElement: any) {
    const {height, width, current} = videoElement
    console.log(height, width, current)
    this._cap = new cv.VideoCapture(current);
    this._ws = new WebSocket("ws://localhost:8080/ws/hello_world")
  }

  processVideo = () => {
    setInterval(() => {
      const image = new cv.Mat(600, 800, cv.CV_8UC4)
      this._cap.read(image);
      // cv.imshow('canvasOutput', image);
      this._ws.send(image.data)
      image.delete()
    }, 10)
  }
}