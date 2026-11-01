import {app, BrowserWindow} from 'electron';

// Playwright adds inspector switches before the application arguments.
const url = process.argv.find(argument => argument.startsWith('http://127.0.0.1:'));
if (!url || !url.startsWith('http://127.0.0.1:')) throw new Error('A local prototype URL is required');
void app.whenReady().then(async () => {
    const window = new BrowserWindow({width: 1200, height: 900, show: process.env.MEDIA_TEST !== '1',
        webPreferences: {contextIsolation: true, nodeIntegration: false, backgroundThrottling: false}});
    await window.loadURL(url);
}).catch((error: unknown) => { console.error(error); app.exit(1); });
app.on('window-all-closed', () => app.quit());
