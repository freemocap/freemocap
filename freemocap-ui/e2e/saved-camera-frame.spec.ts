import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('saved camera scene follows selected geometry without a calibration file or live transform', async ({page}) => {
    const bundle = await build({bundle: true, write: false, platform: 'browser', format: 'esm',
        alias: {'@': resolve('src')}, loader: {'.yaml': 'text'}, define: {'import.meta.env.DEV': 'false'}, stdin: {resolveDir: process.cwd(), loader: 'tsx', contents: `
        import React, {useState} from 'react';
        import {createRoot} from 'react-dom/client';
        import {Provider} from 'react-redux';
        import {store} from './src/store/store';
        import {calibrationFixture} from './e2e/fixtures/calibration';
        import {RecordingSelectionContext} from './src/components/viewport3d/RecordingSelectionContext';
        import {useReferenceFrameForwarder} from './src/components/viewport3d/hooks/useReferenceFrameForwarder';
        import {workerDataStore} from './src/components/viewport3d/WorkerDataStore';
        const raw = calibrationFixture();
        const cameras = raw.cameras.map(camera => ({...camera, world_position: [123, 456, 789]}));
        const target = {postMessage(message) {
            workerDataStore.dispatch(message.type, message.data);
            document.getElementById('scene').textContent = JSON.stringify(workerDataStore.getCalibration());
            document.getElementById('transform').textContent = JSON.stringify(message.data.referenceTransform);
        }};
        function Forward({file}) {useReferenceFrameForwarder(target, false, file); return null;}
        function App() {
            const [file, setFile] = useState(raw);
            const [selected, setSelected] = useState(cameras);
            return <><output id="scene"/><output id="transform"/>
                <button onClick={() => setFile(null)}>Remove calibration file</button>
                <button onClick={() => setSelected(cameras.map(camera => ({...camera, world_position: [900, 800, 700]})))}>Select another result</button>
                <button onClick={() => setSelected([])}>No saved cameras</button>
                <RecordingSelectionContext.Provider value={{cameras: selected}}><Forward file={file}/></RecordingSelectionContext.Provider>
            </>;
        }
        createRoot(document.getElementById('root')).render(<Provider store={store}><App/></Provider>);
    `}});
    page.on('pageerror', error => {throw error;});
    await page.route('https://saved-camera.test/**', route => route.fulfill({contentType: 'text/html',
        body: `<div id="root"></div><script type="module">${bundle.outputFiles[0].text}</script>`}));
    await page.goto('https://saved-camera.test/');
    await expect(page.locator('#scene')).toContainText('[123,456,789]');
    await expect(page.locator('#transform')).toHaveText('null');
    await page.getByRole('button', {name: 'Remove calibration file'}).click();
    await expect(page.locator('#scene')).toContainText('[123,456,789]');
    await page.getByRole('button', {name: 'Select another result'}).click();
    await expect(page.locator('#scene')).toContainText('[900,800,700]');
    await page.getByRole('button', {name: 'No saved cameras'}).click();
    await expect(page.locator('#scene')).toHaveText('{"cameras":[]}');
});
