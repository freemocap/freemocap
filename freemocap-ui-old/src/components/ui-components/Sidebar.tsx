import * as React from 'react';
import Divider from '@mui/material/Divider';
import Drawer, {DrawerProps} from '@mui/material/Drawer';
import List from '@mui/material/List';
import Box from '@mui/material/Box';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import {useNavigate} from "react-router";
import WebsocketConnectionStatus from "@/components/ui-components/WebsocketConnectionStatus";
import {ConnectToCamerasButton} from "@/components/ui-components/ConnectToCamerasButton";

const sidebarItems = [
    {
        id: 'Views',
        children: [
            {
                id: '3d Viewport',
                route: '/'
            },
            {
                id: 'Camera Views',
                route: "/show_cameras"
            },
            // {
            //     id: 'JS Camera',
            //     route: '/jontestplayground'
            // },
            // {
            //   id: "Board Detection",
            //   route: "/charuco_board_detection"
            // },
            // {
            //   id: "Skeleton Detection",
            //   route: "/skeleton_detection"
            // },
            {
                id: "Config View",
                route: "/config"
            }
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

export const Sidebar = function (props: DrawerProps) {
    const {...other} = props;
    const navigate = useNavigate();
    return (
        <Drawer variant="permanent" {...other}>
            <List disablePadding>
                <ListItem sx={{...item, ...itemCategory, fontSize: 22, color: '#fff'}}>
                    FreeMoCap 💀✨
                </ListItem>
                {/*<ListItem sx={{...item, ...itemCategory}}>*/}
                {/*    <ListItemIcon>*/}
                {/*        <HomeIcon/>*/}
                {/*    </ListItemIcon>*/}
                {/*    <ListItemText>Home</ListItemText>*/}
                {/*</ListItem>*/}
                {sidebarItems.map(({id, children}) => (
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
                        <Divider sx={{mt: 2}}/>
                    </Box>
                ))}
            </List>
            <WebsocketConnectionStatus/>
            <ConnectToCamerasButton />

        </Drawer>
)
    ;
}
