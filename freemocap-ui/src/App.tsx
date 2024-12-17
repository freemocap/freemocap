import React from 'react';
import {Paperbase} from "@/layout/paperbase_theme.tsx/Paperbase";
import {useWebSocket} from '@/hooks/useWebsocket';

function App() {
    const _port = 8005;
    const wsURL = `ws://localhost:${_port}/skellycam/websocket/connect`;
    const {isConnected, messages} = useWebSocket(wsURL);
    return (
        <React.Fragment>
            <div>
                <h1>WebSocket Connection</h1>
                <p>Connected: {isConnected ? 'true' : 'false'}</p>
                <h2>Messages</h2>
                <ul>
                    {messages.map((message, index) => (
                        <li key={index}>{message}</li>
                    ))}
                </ul>
            </div>
            <Paperbase/>
        </React.Fragment>
    );
}

export default App;
