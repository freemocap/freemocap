import {Box} from "@mui/material";
import React from "react";
import {ThreeJsCanvas} from "@/components/viewport3d/ThreeJsCanvas";

export const Viewport3d = () => {
    return (
        <Box sx={{display: "flex", flexDirection: "column", height: "81vh"}}>
            {/*<ThreeJSCanvas/>*/}
            <ThreeJsCanvas/>
        </Box>
    );
}
