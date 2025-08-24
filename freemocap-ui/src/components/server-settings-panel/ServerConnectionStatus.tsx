import {Box, Typography} from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import {usePythonServerContext} from "@/context/python-server-context/PythonServerContext";

export const ServerConnectionStatus = () => {
    const {isPythonRunning, startPythonServer, stopPythonServer} = usePythonServerContext();

    const handleToggleConnection = () => {
        if (isPythonRunning) {
            console.log('Toggling Python Server: stopping');
            stopPythonServer();
        } else {
            console.log('Toggling Python Server: starting');
            startPythonServer(null);
        }
    };
    return (

        <Box
            sx={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    padding: '10px',
                    flexDirection: 'column',
                    pl: 4,
                    color: '#dadada',
                    cursor: 'pointer',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    ':hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.05)',
                        borderColor: 'rgba(255, 255, 255, 0.2)',
                    },
                }}
            onClick={handleToggleConnection}
        >
            <Typography
                variant="body1"
                component="div"
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                }}
            >
                <Box sx={{
                    border: '1px solid rgba(255, 255, 255, 0.3)',
                    backgroundColor: isPythonRunning ? 'rgba(0, 255, 255, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                    borderColor: isPythonRunning ? 'rgba(0, 255, 255, 0.5)' : 'rgba(255, 0, 0, 0.5)',

                    width: '24px',
                    height: '24px',
                    marginRight: '8px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}>
                    {isPythonRunning ? (
                        <CheckIcon sx={{color: 'green', fontSize: '16px'}}/>
                    ) : (
                        <CloseIcon fontSize="small" sx={{color: 'red'}}/>
                    )}
                </Box>
                Python Server: {isPythonRunning ? 'running' : 'stopped'}
            </Typography>
        </Box>
    );
};
