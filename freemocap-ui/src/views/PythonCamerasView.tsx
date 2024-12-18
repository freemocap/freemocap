import {Box, Button} from "@mui/material";
import React from "react";
import {ConnectToCamerasButton} from "@/components/ConnectToCamerasButton";

export const PythonCamerasView = () => {

    return (
        <Box sx={{display: "flex", flexDirection: "column"}}>
            <ConnectToCamerasButton/>
        </Box>
    );
}
