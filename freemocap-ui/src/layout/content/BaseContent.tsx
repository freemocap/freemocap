import React from 'react';
import {Header} from "../Header";
import Box from "@mui/material/Box";
import {Router} from "../routing/router";

export const BaseContent = () => {
    return (
        <React.Fragment>
            {/*<Header title="FreeeeMoCap " onDrawerToggle={() => {}}/>*/}
            <Box sx={{py: 6, px: 4, flex: 1, bgcolor: '#9008c6', border: '5px solid black'}}>
                <Router/>
            </Box>
        </React.Fragment>
    )
}
