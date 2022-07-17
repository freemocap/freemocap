export class BrowserCam {
  public async findAllCameras() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(({ kind }) => kind === "videoinput");
  }
}