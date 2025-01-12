import React from "react";
import Webcam from "react-webcam";

export const WebcamCapture = () => {
  const [deviceId, setDeviceId] = React.useState<string>("");
  const [devices, setDevices] = React.useState<MediaDeviceInfo[]>([]);

  const handleDevices = React.useCallback((mediaDevices: MediaDeviceInfo[]) =>
      setDevices(mediaDevices.filter(({ kind }) => kind === "videoinput")),
    [setDevices]
  );

  React.useEffect(
    () => {
      navigator.mediaDevices.enumerateDevices().then(handleDevices);
    },
    [handleDevices]
  );

  return (
    <>
      {devices.map((device, key) => (
        <div>
          <Webcam audio={false} videoConstraints={{ deviceId: device.deviceId }} />
          {device.label || `Device ${device.deviceId}`}
        </div>

      ))}
    </>
  );
};
