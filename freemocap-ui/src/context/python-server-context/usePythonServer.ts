import { useState, useCallback } from "react";

export const usePythonServer = () => {
    const [isPythonRunning, setIsRunning] = useState(false);

    const startPythonServer = useCallback(async (exePath:string|null) => {
        try {
            console.log("Starting Python server...");
            await window.electronAPI.startPythonServer(exePath);
            setIsRunning(true);
        } catch (error) {
            console.error('Failed to start Python server:', error);
        }
    }, []);

    const stopPythonServer = useCallback(async () => {
        try {
            console.log("Stopping Python server...");
            await window.electronAPI.stopPythonServer();
            setIsRunning(false);
        } catch (error) {
            console.error('Failed to stop Python server:', error);
        }
    }, []);

    return {
        isPythonRunning,
        startPythonServer,
        stopPythonServer
    };
};
