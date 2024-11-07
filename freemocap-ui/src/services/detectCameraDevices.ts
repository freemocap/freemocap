export class AvailableCameraDevices {
    public async findAllCameras(filterVirtual: boolean = true) {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const cameras = devices.filter(({kind, label}) => kind === "videoinput");
        console.log(`Found ${cameras.length} cameras - ${cameras.map(({label}) => label).join("\n") }`);
        return filterVirtual ? cameras.filter(({label}) => !this._isVirtualCamera(label)) : cameras;
    }

    private _isVirtualCamera(label: string): boolean {
        const virtualCameraKeywords = ['virtual'];

        return virtualCameraKeywords.some(keyword => label.toLowerCase().includes(keyword));
    }
}
