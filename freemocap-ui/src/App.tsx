import React from 'react';
import {Paperbase} from "@/layout/paperbase_theme.tsx/Paperbase";
import {WebSocketProvider} from "@/context/WebSocketContext";


function App() {
    const _port = 8005;
    const wsUrl = `ws://localhost:${_port}/websocket/connect`;
    return (
        <WebSocketProvider url={wsUrl}>
            <React.Fragment>
                <Paperbase/>
            </React.Fragment>
        </WebSocketProvider>
    );
}

export default App;
