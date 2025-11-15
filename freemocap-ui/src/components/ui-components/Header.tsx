// Update Header.tsx
import * as React from 'react';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import {Box, useTheme} from '@mui/material';
import ThemeToggle from './ThemeToggle';

export const Header = function () {
    const theme = useTheme();

    return (
        <AppBar
            color="primary"
            position="sticky"
            elevation={0}
            sx={{
                borderBottom: '1px solid',
                borderColor: theme.palette.divider
            }}
        >
            <Toolbar>
                <Typography variant="h6" color="inherit" sx={{flexGrow: 1}}>
                    FreeMoCap 💀📸
                </Typography>
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                    <ThemeToggle/>
                </Box>
            </Toolbar>
        </AppBar>
    );
}

export default Header;
