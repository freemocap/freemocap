import { Box, Typography } from "@mui/material";
import React from "react";
import { useAsync } from "react-use";
import { AvailableCameraDevices } from "@/services/detectCameraDevices";
import { useWebSocketContext } from "@/context/WebSocketContext";

export const ConfigView = () => {
    const [devices, setDevices] = React.useState<MediaDeviceInfo[]>([]);
    const { latestSkellyCamAppState } = useWebSocketContext();



    useAsync(async () => {
        const cam = new AvailableCameraDevices();
        const deviceInfos = await cam.findAllCameras(false);
        setDevices(deviceInfos);
    }, []); // Adding an empty dependency array to ensure this runs once on component mount

    const devicesWithNames = devices.filter(x => x.label);


    return (
        <Box>
            <h2>JS Detected Cameras</h2>
            {devicesWithNames.map(device => (
                <Typography key={device.deviceId}>Webcam {device.label}</Typography>
            ))}
            <br/>
            <h2>Latest SkellyCamAppState</h2>
            {latestSkellyCamAppState && (
                <Typography component="pre">
                    {JSON.stringify(latestSkellyCamAppState, null, 2)}
                </Typography>
            )}
        </Box>
    );
}
