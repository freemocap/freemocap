import {Box} from "@mui/material";
import React from "react";
import {ThreeJsCanvas} from "@/components/viewport3d/ThreeJsCanvas";
import {VMCPanel} from "@/components/viewport3d/VMCPanel";

export const Viewport3dPage = () => {
    return (
        <Box sx={{width: '100%', height: '100%', position: 'relative'}}>
            <ThreeJsCanvas/>
            <VMCPanel/>
        </Box>
    );
}
