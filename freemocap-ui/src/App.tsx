import React from 'react';
import { PaperbaseContent } from "@/layout/paperbase_theme/PaperbaseContent";
import { Provider } from "react-redux";
import { AppStateStore } from "@/store/AppStateStore";
import { WebSocketContextProvider } from "@/context/websocket-context/WebSocketContext";
import { urlService } from '@/services/urlService';

function App() {
    const wsUrl = urlService.getWebSocketUrl();
    return (
        <Provider store={AppStateStore}>
                <WebSocketContextProvider url={wsUrl}>
                    <PaperbaseContent/>
                </WebSocketContextProvider>
        </Provider>
    );
}

export default App;

