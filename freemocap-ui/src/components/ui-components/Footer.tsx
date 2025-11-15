// Update Copyright.tsx
import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";
import * as React from "react";
import {useTheme} from "@mui/material";

export const Footer = function () {
    const theme = useTheme();

    return (
        <Typography
            variant="body2"
            color={theme.palette.mode === 'dark' ? "rgba(255,255,255,0.7)" : "rgba(0,0,0,0.6)"}
            align="center"
        >
            {'w/ '}
            <Link color="inherit" href="https://github.com/freemocap/">
                ❤️
            </Link>{'  from the '}
            <Link color="inherit" href="https://github.com/freemocap/">
                FreeMoCap Foundation
            </Link>{' '}
            {new Date().getFullYear()}
        </Typography>
    );
}
