import React from "react";
import Webcam from "react-webcam";

export const WebcamCapture = () => {
  const [deviceId, setDeviceId] = React.useState<any>({});
  const [devices, setDevices] = React.useState<any>([]);

  const handleDevices = React.useCallback(mediaDevices =>
      // @ts-ignore
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
          {device.label || `Device ${key + 1}`}
        </div>

      ))}
    </>
  );
};