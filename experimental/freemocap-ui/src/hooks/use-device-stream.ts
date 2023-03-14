import {useAsync} from "react-use";

export const useDeviceStream = (device: MediaDeviceInfo) => {
  const {value} = useAsync(async () => {
    return await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: device.deviceId
      },
    })
  }, [device])
  return value
}