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
import {useNavigate} from "react-router";

const categories = [
  {
    id: 'Interact',
    children: [
      {
        id: 'Session',
        route: "/session"
      },
      {
        id: 'Setup and Preview',
        route: "/setup_and_preview"
      },
      {
        id: 'Show Cameras',
        route: "/show_cameras"
      },
    ],
  },
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
          freemocap
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
            {children.map(({id: childId, route}) => (
              <ListItem disablePadding key={childId}>
                <ListItemButton selected={false} sx={item} onClick={() => {
                  navigate(route)
                }}>
                  {/*<ListItemIcon>{icon}</ListItemIcon>*/}
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