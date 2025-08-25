import * as React from 'react';
import Box from '@mui/material/Box';
import {SimpleTreeView} from '@mui/x-tree-view/SimpleTreeView';
import {TreeItem} from '@mui/x-tree-view/TreeItem';
import {Checkbox, FormControlLabel, Slider, TextField, Typography} from '@mui/material';
import WebsocketConnectionStatus from './WebsocketConnectionStatus';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {ServerConnectionStatus} from "@/components/server-settings-panel/ServerConnectionStatus";


export const ServerSettingsPanel = () => {
    const {isConnected} = useWebSocketContext();
    const [startServer, setStartServer] = React.useState(true);
    const [serverExecutablePath, setServerExecutablePath] = React.useState('/path/to/server/executable');
    const [host, setHost] = React.useState('localhost');
    const [httpPort, setHttpPort] = React.useState(8006);
    const [limitFramerate, setLimitFramerate] = React.useState(false);
    const [framerate, setFramerate] = React.useState(30);
    const [preShrink, setPreShrink] = React.useState(true);
    const [shrinkFactor, setShrinkFactor] = React.useState(0.5);

    const maxFramerate = 60;

    const handleFramerateChange = (event: Event, newValue: number | number[]) => {
        setFramerate(newValue as number);
    };

    const handleShrinkFactorChange = (event: Event, newValue: number | number[]) => {
        setShrinkFactor(newValue as number);
    };

    return (
        <Box sx={{padding: 2, color: 'text.primary'}}>
            <SimpleTreeView
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon
                }}
                sx={{flexGrow: 1, maxWidth: 400}}
            >
                <TreeItem
                    itemId="server-status"
                    label={
                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                            <span>Server status:</span>
                            <Box
                                sx={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    bgcolor: isConnected ? 'rgba(0, 255, 255, 0.25)' : 'rgba(255, 0, 0, 0.25)',
                                    px: 1,
                                    py: 0.5,
                                    borderRadius: 1
                                }}
                            >
                                {isConnected ? 'Connected' : 'Disconnected'}
                            </Box>
                        </Box>
                    }
                >
                    <Box sx={{pl: 2, pt: 1, borderTop: '2px solid', borderColor: 'darkcyan'}}>
                        <ServerConnectionStatus/>
                        <WebsocketConnectionStatus/>
                        <TreeItem itemId="server-settings" label="Server Settings"  disabled={true}>
                            <Box sx={{pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2}}>
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={startServer}
                                            onChange={(e) => setStartServer(e.target.checked)}
                                        />
                                    }
                                    label="Start server executable"
                                />

                                <TextField
                                    label="Server executable path"
                                    value={serverExecutablePath}
                                    onChange={(e) => setServerExecutablePath(e.target.value)}
                                    fullWidth
                                    size="small"
                                />

                                <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                                    <TextField
                                        label="Host"
                                        value={host}
                                        onChange={(e) => setHost(e.target.value)}
                                        size="small"
                                        sx={{flex: 1}}
                                    />
                                    <TextField
                                        label="HTTP Port"
                                        type="number"
                                        value={httpPort}
                                        onChange={(e) => setHttpPort(Number(e.target.value))}
                                        size="small"
                                        sx={{width: 100}}
                                    />
                                </Box>

                                <Typography variant="body2" color="textSecondary">
                                    WebSocket URL: ws://{host}:{httpPort}/websocket/connect
                                </Typography>
                            </Box>
                        </TreeItem>

                        <TreeItem itemId="display-settings" label="Display Settings"  disabled={true}>
                            <Box sx={{pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2}}>
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={limitFramerate}
                                            onChange={(e) => setLimitFramerate(e.target.checked)}
                                        />
                                    }
                                    label="Limit display framerate"
                                />

                                {limitFramerate && (
                                    <Box sx={{pl: 4}}>
                                        <Typography gutterBottom>
                                            Framerate: {framerate} FPS
                                        </Typography>
                                        <Slider
                                            value={framerate}
                                            onChange={handleFramerateChange}
                                            min={0}
                                            max={maxFramerate}
                                            valueLabelDisplay="auto"
                                            size="small"
                                        />
                                    </Box>
                                )}

                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={preShrink}
                                            onChange={(e) => setPreShrink(e.target.checked)}
                                        />
                                    }
                                    label="Pre-shrink images"
                                />

                                {preShrink && (
                                    <Box sx={{pl: 4}}>
                                        <Typography gutterBottom>
                                            Shrink factor: {shrinkFactor.toFixed(2)}
                                        </Typography>
                                        <Slider
                                            value={shrinkFactor}
                                            onChange={handleShrinkFactorChange}
                                            min={0}
                                            max={1}
                                            step={0.01}
                                            valueLabelDisplay="auto"
                                            size="small"
                                        />
                                    </Box>
                                )}
                            </Box>
                        </TreeItem>
                    </Box>
                </TreeItem>
            </SimpleTreeView>
        </Box>
    );
};
