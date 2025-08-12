import {Paper} from "@mui/material";
import React from "react";

export const BasePaper = (props: any) => {
  const { children, ...rest} = props;
  return (
    <Paper sx={{ maxWidth: 936, margin: 'auto', overflow: 'hidden', ...rest }}>
      {props.children}
    </Paper>
  )
}
