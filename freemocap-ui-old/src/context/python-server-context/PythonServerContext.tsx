import React, { createContext, useContext, ReactNode } from "react";
import { usePythonServer } from "./usePythonServer";

interface PythonServerContextProps {
    isPythonRunning: boolean;
    startPythonServer: (exePath:string|null) => void;
    stopPythonServer: () => void;
}

const PythonServerContext = createContext<PythonServerContextProps | undefined>(undefined);

interface PythonServerProviderProps {
    children: ReactNode;
}

export const PythonServerContextProvider: React.FC<PythonServerProviderProps> = ({ children }) => {
    const pythonServer = usePythonServer();

    return (
        <PythonServerContext.Provider value={pythonServer}>
            {children}
        </PythonServerContext.Provider>
    );
};

export const usePythonServerContext = () => {
    const context = useContext(PythonServerContext);
    if (!context) {
        throw new Error('usePythonServerContext must be used within a PythonServerProvider');
    }
    return context;
};
