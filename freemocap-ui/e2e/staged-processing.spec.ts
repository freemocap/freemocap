import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer} from 'node:http';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('saved stages default to resume, enforce dependencies, and reset for another recording', async ({page}, testInfo) => {
    const uiRoot = fileURLToPath(new URL('../', import.meta.url));
    const bundle = await build({bundle: true, write: false, outdir: 'staged-test', format: 'esm', platform: 'browser',
        absWorkingDir: uiRoot, alias: {'@': resolve(uiRoot, 'src')}, define: {'import.meta.env.DEV': 'false'},
        stdin: {resolveDir: uiRoot, loader: 'tsx', contents: `
            import React, {useState} from 'react'; import {createRoot} from 'react-dom/client';
            import Stages from './src/components/mocap-setup/mocap-stage-selection';
            import {serverUrls} from './src/constants/server-urls';
            serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
            function App() {
                const [path, setPath] = useState('partial'); const [selection, setSelection] = useState(null);
                return <main><h1>Processing stages</h1><select aria-label="Recording" value={path} onChange={e => setPath(e.target.value)}>
                    <option>partial</option><option>complete</option><option>new</option><option>broken</option></select>
                    <Stages path={path} onChange={setSelection}/>
                    <button disabled={!selection}>Process Mocap</button><output>{JSON.stringify(selection)}</output></main>;
            }
            createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
        `}});
    const server = createServer((request, response) => {
        if (request.url?.includes('/process/stages?')) {
            const path = new URL(request.url, 'http://localhost').searchParams.get('recording_path');
            response.writeHead(path === 'broken' ? 400 : 200, {'Content-Type': 'application/json'});
            response.end(JSON.stringify(path === 'broken' ? {detail: 'Unreadable recording'} : {
                selected_run_id: 2, runs: path === 'new' ? [] : [{run_id: 2, groups: [{sensor_group: 'camera_group:test', stages: {
                    observations: true, triangulation: true, filtering: path === 'complete',
                    scale_fit: path === 'complete', reconstruction: path === 'complete',
                }}]}],
            }));
        } else if (request.url === '/entry.js') {
            response.setHeader('Content-Type', 'text/javascript'); response.end(bundle.outputFiles.find(file => file.path.endsWith('.js'))!.text);
        } else response.end(`<style>body{font:16px system-ui;background:#16191d;color:#eef1f4;padding:32px}main{max-width:760px}label{display:block;padding:12px;border-bottom:1px solid #444}p{line-height:1.5;color:#bbc3ce}button,select{padding:8px;margin:12px 0}output{display:block;font:12px monospace}</style><div id="root"></div><script type="module" src="/entry.js"></script>`);
    });
    await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
    try {
        const address = server.address(); if (!address || typeof address === 'string') throw new Error('No address');
        await page.goto(`http://127.0.0.1:${address.port}`);
        const tracking = page.getByRole('checkbox', {name: /2D tracking/});
        const triangulation = page.getByRole('checkbox', {name: /Triangulation/});
        const filtering = page.getByRole('checkbox', {name: /Gap filling/});
        const reconstruction = page.getByRole('checkbox', {name: /Skeleton reconstruction/});
        await expect(tracking).not.toBeChecked();
        await expect(triangulation).not.toBeChecked();
        await expect(filtering).toBeChecked();
        await expect(reconstruction).toBeChecked();
        await expect(reconstruction).toBeEnabled();
        await page.getByRole('combobox', {name: 'Save results', exact: true}).selectOption('new_run');
        await expect(page.locator('output')).toContainText('"runSaveMode":"new_run"');
        await expect(page.locator('p[role="status"]')).toContainText('Read from Run 2');
        await page.screenshot({path: testInfo.outputPath('new-run-selection.png'), fullPage: true});
        await page.getByRole('combobox', {name: 'Save results', exact: true}).selectOption('overwrite');
        await expect(page.locator('output')).toContainText('"runSaveMode":"overwrite"');
        await reconstruction.uncheck();
        await expect(page.locator('output')).toContainText('"stopStage":"scale_fit"');
        await expect(filtering).toBeChecked();
        await expect(page.locator('output')).toContainText('"startStage":"filtering"');
        await triangulation.check();
        await expect(page.locator('output')).toContainText('"startStage":"triangulation"');
        await expect(filtering).toBeEnabled();
        await expect(reconstruction).toBeChecked();
        await filtering.uncheck();
        await expect(page.locator('output')).toContainText('"stopStage":"triangulation"');
        await expect(reconstruction).not.toBeChecked();
        await page.getByLabel('Recording', {exact: true}).selectOption('complete');
        await expect(page.getByRole('button', {name: 'Process Mocap'})).toBeDisabled();
        await reconstruction.check();
        await expect(page.locator('output')).toContainText('"startStage":"reconstruction"');
        await expect(page.locator('output')).toContainText('"baseRunId":2');
        await expect(triangulation).not.toBeChecked();
        await page.screenshot({path: testInfo.outputPath('staged-processing.png'), fullPage: true});
        await page.getByLabel('Recording', {exact: true}).selectOption('new');
        await expect(tracking).toBeChecked();
        await expect(tracking).toBeEnabled();
        await expect(page.locator('output')).toContainText('"startStage":"observations"');
        await expect(page.locator('output')).toContainText('"baseRunId":0');
        await tracking.uncheck();
        await expect(page.getByRole('button', {name: 'Process Mocap'})).toBeDisabled();
        await expect(triangulation).toBeDisabled();
        await tracking.check();
        await expect(reconstruction).toBeChecked();
        await page.getByLabel('Recording', {exact: true}).selectOption('broken');
        await expect(page.getByRole('alert')).toContainText('Unreadable recording');
        await expect(page.getByRole('button', {name: 'Process Mocap'})).toBeDisabled();
    } finally {
        await page.goto('about:blank');
        await new Promise<void>(done => {
            server.close(() => done());
            // Close browser keep-alive sockets before awaiting server shutdown.
            server.closeAllConnections();
        });
    }
});
