import {Box} from "@mui/material";
import React from "react";
import {ThreeJsCanvas} from "@/components/viewport3d/ThreeJsCanvas";

export const Viewport3dPage = () => {
    return (
        <Box sx={{width: '100%',
            height: '100%',
        }}>
            <ThreeJsCanvas/>
        </Box>
    );
}
