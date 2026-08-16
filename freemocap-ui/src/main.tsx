import React from 'react'
import ReactDOM from 'react-dom/client'

import './index.css'
import {initializeI18n} from './i18n'

async function bootstrap(): Promise<void> {
    await initializeI18n()
    const {default: App} = await import('./app/App')

    ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
        <React.StrictMode>
            <App/>
        </React.StrictMode>,
    )

    postMessage({payload: 'removeLoading'}, '*')
}

void bootstrap()
