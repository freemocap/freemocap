import * as React from 'react';
import Divider from '@mui/material/Divider';
import Drawer, {DrawerProps} from '@mui/material/Drawer';
import List from '@mui/material/List';
import Box from '@mui/material/Box';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import HomeIcon from '@mui/icons-material/Home';
import PeopleIcon from '@mui/icons-material/People';
import {useNavigate} from "react-router";

const categories = [
  {
    id: 'Build',
    children: [
      {
        id: 'Show Cameras',
        icon: <PeopleIcon />,
        active: true,
      },
      // { id: 'Database', icon: <DnsRoundedIcon /> },
      // { id: 'Storage', icon: <PermMediaOutlinedIcon /> },
      // { id: 'Hosting', icon: <PublicIcon /> },
      // { id: 'Functions', icon: <SettingsEthernetIcon /> },
      // {
      //   id: 'Machine learning',
      //   icon: <SettingsInputComponentIcon />,
      // },
    ],
  },
  // {
  //   id: 'Quality',
  //   children: [
  //     { id: 'Analytics', icon: <SettingsIcon /> },
  //     { id: 'Performance', icon: <TimerIcon /> },
  //     { id: 'Test Lab', icon: <PhonelinkSetupIcon /> },
  //   ],
  // },
];

const item = {
  py: '2px',
  px: 3,
  color: 'rgba(255, 255, 255, 0.7)',
  '&:hover, &:focus': {
    bgcolor: 'rgba(255, 255, 255, 0.08)',
  },
};

const itemCategory = {
  boxShadow: '0 -1px 0 rgb(255,255,255,0.1) inset',
  py: 1.5,
  px: 3,
};

export const Navigator = function (props: DrawerProps) {
  const {...other} = props;
  const navigate = useNavigate();
  return (
    <Drawer variant="permanent" {...other}>
      <List disablePadding>
        <ListItem sx={{...item, ...itemCategory, fontSize: 22, color: '#fff'}}>
          FreeMoCap
        </ListItem>
        <ListItem sx={{...item, ...itemCategory}}>
          <ListItemIcon>
            <HomeIcon />
          </ListItemIcon>
          <ListItemText>Overview</ListItemText>
        </ListItem>
        {categories.map(({id, children}) => (
          <Box key={id} sx={{bgcolor: '#101F33'}}>
            <ListItem sx={{py: 2, px: 3}}>
              <ListItemText sx={{color: '#fff'}}>{id}</ListItemText>
            </ListItem>
            {children.map(({id: childId, icon, active}) => (
              <ListItem disablePadding key={childId}>
                <ListItemButton selected={active} sx={item} onClick={() => {
                  navigate("/show_cameras")
                }}>
                  <ListItemIcon>{icon}</ListItemIcon>
                  <ListItemText>{childId}</ListItemText>
                </ListItemButton>
              </ListItem>
            ))}
            <Divider sx={{mt: 2}} />
          </Box>
        ))}
      </List>
    </Drawer>
  );
}