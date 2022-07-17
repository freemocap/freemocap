import axios from "axios";

export type DeviceId = string;
export type StreamByDeviceId = Record<DeviceId, MediaStream>;
export type RecorderByDeviceId = Record<DeviceId, MediaRecorder>;
export type StreamDataByDeviceId = Record<DeviceId, Blob[]>;

export class RecorderManager {
  private _recordedData: StreamDataByDeviceId = {};
  private readonly _recorders: RecorderByDeviceId;
  private readonly _deviceIds: Array<DeviceId>;
  private readonly _timesliceInMs: number;

  constructor(streams: StreamByDeviceId, timesliceInMS: number = 500) {
    this._timesliceInMs = timesliceInMS;
    this._deviceIds = (Object.keys(streams) as Array<DeviceId>);
    this._recorders = this._deviceIds.reduce((prev, curDeviceId) => {
      return {
        ...prev,
        [curDeviceId]: new MediaRecorder(streams[curDeviceId])
      }
    }, {});
    this._init_recorded_data();
  }

  private _init_recorded_data() {
    const deviceIds = this._deviceIds;
    deviceIds.forEach(deviceId => {
      this._recordedData[deviceId] = [];
    });
  }

  public registerDataHandler = () => {
    const deviceIds = this._deviceIds;
    deviceIds.forEach(deviceId => {
      const recorder = this._recorders[deviceId];
      recorder.ondataavailable = (event) => {
        this._recordedData[deviceId].push(event.data)
      }
    })
  }

  public start = () => {
    const deviceIds = this._deviceIds;
    deviceIds.forEach(deviceId => {
      const recorder = this._recorders[deviceId];
      recorder.start(this._timesliceInMs)
    })
  }

  public stop = () => {
    const deviceIds = this._deviceIds;
    deviceIds.forEach(deviceId => {
      const recorder = this._recorders[deviceId];
      recorder.stop()
    });
  }

  public process = async () => {
    const deviceIds = this._deviceIds;
    for (const deviceId of deviceIds) {
        const blobChunks = this._recordedData[deviceId];
        const combinedBlob = new Blob(blobChunks, {type: "video/webm"});
        await axios.post('http://localhost:8080/camera/upload', combinedBlob);
    }
  }
}

