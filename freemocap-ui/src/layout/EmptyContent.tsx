import React from 'react';
import {Paper} from "@mui/material";
import {Header} from "./Header";
import Box from "@mui/material/Box";

export const EmptyContent = () => {
  return (
    <React.Fragment>
      <Header title={"Something"} onDrawerToggle={() => {}} />
      <Box sx={{ py: 6, px: 4,  flex: 1, bgcolor: '#eaeff1' }}>
        <Paper sx={{ maxWidth: 936, margin: 'auto', overflow: 'hidden' }}>
        </Paper>
      </Box>
    </React.Fragment>
  )
}