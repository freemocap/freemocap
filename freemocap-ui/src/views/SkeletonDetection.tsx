import React from "react";
import {Box} from "@mui/material";
import {CaptureType} from "../services/websocket-connection";
import {useWebsocket} from "../hooks/use-websocket";

export const SkeletonDetection = () => {
    // const [frameCapture, data] = useWebsocket(CaptureType.SkeletonDetection, 8080,);
    // if (!data) {
    //     return null;
    // }
    // return (
    //     <Box>
    //         {!frameCapture.isConnectionClosed && <img src={frameCapture.current_data_url} alt={"video capture"}/>}
    //     </Box>
    // );
}