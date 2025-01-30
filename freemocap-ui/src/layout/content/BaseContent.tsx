import React from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Router} from "@/layout/routing/router";

export const BaseContent = () => {
    return (
        <React.Fragment>
            {/*<Header title="FreeeeMoCap " onDrawerToggle={() => {}}/>*/}
            <Box sx={{
                py: 6,
                px: 4,
                flex: 1,
                bgcolor: '#113157', border: '1px solid charcoal'
            }}>
                <ErrorBoundary>
                    <Router/>
                </ErrorBoundary>
            </Box>
        </React.Fragment>
    )
}
