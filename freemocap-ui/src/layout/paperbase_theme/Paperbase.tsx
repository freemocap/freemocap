import * as React from 'react';
import {createTheme, ThemeProvider} from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import Box from '@mui/material/Box';
import {HashRouter} from 'react-router-dom';
import {CssBaseline} from "@mui/material";
import paperbaseTheme from '../content/paperbase-theme';
import {Sidebar} from "@/layout/Sidebar";
import {BaseContent} from "@/layout/content/BaseContent";
import {Copyright} from "@/layout/Copyright";
import IconButton from "@mui/material/IconButton";
import MenuIcon from "@mui/icons-material/Menu";

const fullSidebarWidth = '20vw';
const collapsedSidebarWidth = '0vw';

export const Paperbase = function () {
  const [collapsed, setCollapsed] = React.useState(false);

  const handleCollapseToggle = () => {
    setCollapsed(!collapsed);
  }

  return (
    <ThemeProvider theme={paperbaseTheme}>
      <CssBaseline />
      <HashRouter>
        <Box sx={{display: 'flex', minHeight: '100vh', minWidth: collapsed ? '80vw' : '100vw', border:'black'}}>
          <Box
            component="nav"
            sx={{width: collapsed ? collapsedSidebarWidth : fullSidebarWidth, flexShrink: 0}}
          >
            <Sidebar
              PaperProps={{style: {width: collapsed ? collapsedSidebarWidth : fullSidebarWidth}}}
            />
          </Box>

          <Box sx={{flex: 1, display: 'flex', flexDirection: 'column'}}>
            <Box component="main" sx={{flex: 1, bgcolor: '#081627'}}>
              <IconButton
                color="primary"
                aria-label={collapsed ? 'expand' : 'collapse'}
                onClick={handleCollapseToggle}
                sx={{ marginLeft: 1}}
                >
                <MenuIcon />
                </IconButton>
              <BaseContent />
            </Box>
            <Box component="footer" sx={{p: 1, bgcolor: '#081627'}}>
              <Copyright />
            </Box>
          </Box>
        </Box>
      </HashRouter>
    </ThemeProvider>
  );
}
