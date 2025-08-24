import React from 'react';
import { PaperbaseContent } from "@/layout/paperbase_theme/PaperbaseContent";
import { Provider } from "react-redux";
import { AppStateStore } from "@/store/AppStateStore";
import { WebSocketContextProvider } from "@/context/websocket-context/WebSocketContext";
import { urlService } from '@/services/urlService';
import {PythonServerContextProvider} from "@/context/python-server-context/PythonServerContext";

function App() {
    return (
        <Provider store={AppStateStore}>
            <PythonServerContextProvider>
                <WebSocketContextProvider>
                    <PaperbaseContent/>
                </WebSocketContextProvider>
            </PythonServerContextProvider>
        </Provider>
    );
}

export default App;

