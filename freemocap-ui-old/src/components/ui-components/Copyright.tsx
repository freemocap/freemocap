import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";
import * as React from "react";

export const Copyright =  function() {
  return (
    <Typography variant="body2" color="#696969" align="center">
      {'Copyright © '}
      <Link color="inherit" href="https://github.com/freemocap/">
        FreeMoCap Foundation
      </Link>{' '}
      {new Date().getFullYear()}.
    </Typography>
  );
}
