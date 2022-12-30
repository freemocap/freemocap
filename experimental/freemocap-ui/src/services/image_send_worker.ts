const webSocket = new WebSocket("ws://localhost:8080/ws/hello_world")

export const sendImageByRef = (camRef) => {
  const imageSrc = camRef.current.getScreenshot({
    height: 1080,
    width: 1920,
  });
  webSocket.send(imageSrc)
}

export const sendImageByDevice = async (device: MediaDeviceInfo) => {
  // const stream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: device.deviceId}})
  // if (webSocket.readyState === WebSocket.OPEN) {
  //   webSocket.send(frame)
  // }
}