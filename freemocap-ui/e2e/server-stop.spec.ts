import {test, expect, type Page} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

async function mountPanel(page: Page, electron: boolean, owned: boolean, port = 54329): Promise<void> {
    await page.setContent('<div id="root"></div>');
    await page.evaluate(({electron, owned, port}) => {
        Object.assign(window, {panelTest: {electron, owned, port, ipcStops: 0}});
    }, {electron, owned, port});
    const bundle = await build({
        stdin: {resolveDir: path.resolve('.'), loader: 'tsx', contents: `
            import React from 'react';
            import {createRoot} from 'react-dom/client';
            import {ServerConnectionStatus} from './src/components/control-panels/server-connection/ServerConnectionStatus';
            createRoot(document.getElementById('root')!).render(<ServerConnectionStatus />);
        `},
        bundle: true, write: false, format: 'esm', alias: {'@': path.resolve('src')},
        define: {'import.meta.env.DEV': 'true'},
        plugins: [{name: 'panel-boundaries', setup(builder) {
            builder.onResolve({filter: /^(react-i18next|@\/services|@\/services\/server\/ServerContextProvider|@\/store(?:\/.*)?)$/},
                args => ({path: args.path, namespace: 'panel-stub'}));
            builder.onLoad({filter: /.*/, namespace: 'panel-stub'}, args => {
                if (args.path === 'react-i18next') return {loader: 'ts', contents: `
                    const t = (key) => ({connected: 'Connected', stopServer: 'Stop server', launchServer: 'Launch server'}[key] ?? key);
                    export const useTranslation = () => ({t});
                `};
                if (args.path.startsWith('@/store')) return {loader: 'ts', contents: `
                    export const selectServerPid = () => 1234;
                    export const useAppSelector = () => 1234;
                `};
                return {loader: 'ts', resolveDir: path.resolve('.'), contents: `
                    import {serverUrls} from './src/constants/server-urls';
                    export {serverUrls};
                    const controls = window.panelTest;
                    const api = {pythonServer: {
                        isRunning: {query: async () => controls.owned},
                        getProcessInfo: {query: async () => controls.owned ? {pid: 1234, killed: false} : null},
                        getExecutablePath: {query: async () => null},
                        getExecutableCandidates: {query: async () => []},
                        stop: {mutate: async () => {controls.ipcStops++;}},
                    }};
                    export const useElectronIPC = () => ({isElectron: controls.electron, api: controls.electron ? api : null});
                    const connection = {isConnected: true, isFailed: false, connectedCameraIds: [],
                        connect() {}, disconnect() {}, updateServerConnection() {
                            serverUrls.setHost('127.0.0.1'); serverUrls.setPort(controls.port);
                        }};
                    export const useServer = () => connection;
                `};
            });
        }}],
    });
    await page.addScriptTag({content: bundle.outputFiles[0].text, type: 'module'});
    await page.getByRole('button', {name: 'Connected', exact: true}).click();
}

for (const mode of [
    {name: 'Electron-owned backend', electron: true, owned: true},
    {name: 'externally launched backend in Electron', electron: true, owned: false},
    {name: 'externally launched backend in browser', electron: false, owned: false},
]) {
    test(`Stop server requests HTTP shutdown for ${mode.name}`, async ({page}) => {
        const requests: string[] = [];
        await page.route('http://127.0.0.1:54329/shutdown', async route => {
            requests.push(route.request().method());
            await route.fulfill({json: {status: 'shutdown_initiated'}, headers: {'access-control-allow-origin': '*'}});
        });
        await mountPanel(page, mode.electron, mode.owned);
        const button = page.getByRole('button', {name: 'Stop server', exact: true}).first();
        await expect(button).toBeEnabled();
        await button.click();
        await expect.poll(() => requests).toEqual(['GET']);
        expect(await page.evaluate(() => (window as any).panelTest.ipcStops)).toBe(0);
        await expect(page.getByRole('status')).toContainText('Shutdown requested');
    });
}

test('HTTP shutdown failure stays visible and permits retry in browser', async ({page}) => {
    let attempts = 0;
    await page.route('http://127.0.0.1:54329/shutdown', async route => {
        attempts++;
        await route.fulfill({status: attempts === 1 ? 503 : 200,
            json: {status: 'shutdown_initiated'}, headers: {'access-control-allow-origin': '*'}});
    });
    await mountPanel(page, false, false);
    const button = page.getByRole('button', {name: 'Stop server', exact: true}).first();
    await button.click();
    await expect(page.getByRole('alert')).toContainText('503');
    await expect(button).toBeEnabled();
    await button.click();
    await expect(page.getByRole('status')).toContainText('Shutdown requested');
    await expect(page.getByRole('alert')).toHaveCount(0);
    expect(attempts).toBe(2);
});

test('pending shutdown disables both buttons and never falls back to killing a process', async ({page}) => {
    let requests = 0;
    let releaseRequest!: () => void;
    const pending = new Promise<void>(resolve => {releaseRequest = resolve;});
    await page.route('http://127.0.0.1:54329/shutdown', async route => {
        requests++;
        await pending;
        await route.abort('failed');
    });
    await mountPanel(page, true, true);
    const buttons = page.getByRole('button', {name: 'Stop server', exact: true});
    await buttons.first().click();
    await expect(buttons.first()).toBeDisabled();
    await expect(buttons.last()).toBeDisabled();
    releaseRequest();
    await expect(page.getByRole('alert')).toContainText('Stop failed:');
    await expect(buttons.first()).toBeEnabled();
    expect(requests).toBe(1);
    expect(await page.evaluate(() => (window as any).panelTest.ipcStops)).toBe(0);
});

// Explicit opt-in: this test stops the backend at the supplied port.
// Use an isolated test-managed server, never a shared user session.
if (process.env.FREEMOCAP_SHUTDOWN_TEST_PORT) {
    test('real external backend exits after the panel requests shutdown', async ({page, request}) => {
        const port = Number(process.env.FREEMOCAP_SHUTDOWN_TEST_PORT);
        const baseUrl = `http://127.0.0.1:${port}`;
        expect((await request.get(`${baseUrl}/health`)).ok()).toBe(true);
        await page.goto(`${baseUrl}/docs`);
        await mountPanel(page, false, false, port);
        await page.getByRole('button', {name: 'Stop server', exact: true}).click();
        await expect(page.getByRole('status')).toContainText('Shutdown requested');
        await expect.poll(async () => {
            try { return (await request.get(`${baseUrl}/health`, {timeout: 1000})).ok(); }
            catch { return false; }
        }, {timeout: 15000}).toBe(false);
    });
}
