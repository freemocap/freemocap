import {useContext} from "react";
import {ServerContext, ServerContextValue} from "@/services";

export const useServer = (): ServerContextValue => {
    const context = useContext(ServerContext);
    if (!context) {
        throw new Error('useServer must be used within ServerContextProvider');
    }
    return context;
};
