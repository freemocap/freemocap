import Webcam from "react-webcam";
import {useAsync} from "react-use";
import React from "react";
import {Box, Typography} from "@mui/material";
import {AvailableCameraDevices} from "@/services/detectCameraDevices";

export const BrowserCamerasView = () => {
    const [cams, setCams] = React.useState<MediaDeviceInfo[]>([]);

    useAsync(async () => {
        const foundCams = await new AvailableCameraDevices().findAllCameras();
        setCams(foundCams);
    }, []);

    const supportedConstraints = navigator.mediaDevices.getSupportedConstraints();

    const constraints: MediaStreamConstraints = {
        video: {
            exposureMode: "manual",
            exposureCompensation: "-3"
        } as any
    };

    return (
        <Box display="flex" flexWrap="wrap">
            {cams.map((cam, index) => (
                <Box key={index} m={1} position={"relative"}>
                    <Webcam videoConstraints={{...constraints.video as object, deviceId: cam.deviceId}}/>
                    <Box position={"absolute"} bottom={0} left={0} bgcolor="rgba(0,0,0,0.5)" color="white" p={1}>
                        <Typography variant="body2">{cam.label}</Typography>
                        <Typography variant="body2">Device ID: {cam.deviceId}</Typography>
                    </Box>
                </Box>
            ))}
            <Box width="100%">
                <pre>
                    {`Supported constraints:\n ${JSON.stringify(supportedConstraints, null, 2)}`}
                    {`Current Constraints:\n ${JSON.stringify(constraints, null, 2)}`}
                    {`Cameras:\n ${JSON.stringify(cams, null, 2)}`}
                </pre>
            </Box>
        </Box>
    );
};
