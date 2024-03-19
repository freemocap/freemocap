export class BrowserCam {
  public async findAllCameras(filterVirtual: boolean = false) {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const cameras = devices.filter(({ kind, label }) => kind === "videoinput");

    return filterVirtual ? cameras.filter(({ label }) => !this._isVirtualCamera(label)) : cameras;
  }

  private _isVirtualCamera(label: string): boolean {
    const virtualCameraKeywords = ['virtual', 'obs', 'camtwist', 'xsplit', 'v4l2loopback', 'fake'];
    return virtualCameraKeywords.some(keyword => label.toLowerCase().includes(keyword));
  }
}
