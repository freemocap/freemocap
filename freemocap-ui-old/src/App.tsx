import React from 'react';
import {Provider} from 'react-redux';
import {store} from '@/store';
import {ServerContextProvider} from "@/services/server/ServerContextProvider";
import {AppContent} from "@/layout/AppContent";


function App() {
    return (
        <Provider store={store}>
            <ServerContextProvider>
                <AppContent/>
            </ServerContextProvider>
        </Provider>
    );
}

export default App;
