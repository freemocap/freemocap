import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer} from 'node:http';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});
for (const failed of [false, true]) test(`Blender detection stops after ${failed ? 'failure' : 'not found'} and allows manual retry`, async ({page}) => {
    const bundle = await build({bundle: true, write: false, format: 'esm', platform: 'browser',
        alias: {'@': resolve('src')}, loader: {'.yaml': 'text'}, define: {'import.meta.env.DEV': 'false'},
        stdin: {resolveDir: process.cwd(), loader: 'tsx', contents: `
            import React from 'react'; import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux'; import {store} from './src/store/store';
            import {useBlender} from './src/hooks/useBlender';
            import {serverUrls} from './src/constants/server-urls';
            serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
            function Controls(){const b=useBlender(); return <button onClick={b.redetectBlender} disabled={b.isDetecting}>Detect</button>}
            createRoot(document.getElementById('root')).render(<React.StrictMode><Provider store={store}><Controls/><Controls/></Provider></React.StrictMode>);
        `}});
    let requests = 0;
    const server = createServer((request, response) => {
        if (request.url?.includes('/blender/detect')) {
            requests++;
            response.writeHead(failed ? 500 : 200, {'Content-Type':'application/json'});
            response.end(JSON.stringify(failed ? {detail:'test failure'} : {found:false, blender_exe_path:null}));
        } else if (request.url === '/entry.js') {
            response.setHeader('Content-Type','text/javascript'); response.end(bundle.outputFiles[0].text);
        } else response.end('<div id="root"></div><script type="module" src="/entry.js"></script>');
    });
    await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
    try {
        const address = server.address(); if (!address || typeof address === 'string') throw new Error('No address');
        await page.goto(`http://127.0.0.1:${address.port}`);
        const button = page.getByRole('button', {name:'Detect'}).first();
        await expect(button).toBeEnabled();
        await expect.poll(() => requests).toBe(1);
        await page.waitForTimeout(300);
        expect(requests).toBe(1);
        await button.click();
        await expect.poll(() => requests).toBe(2);
        await expect(button).toBeEnabled();
        await page.waitForTimeout(300);
        expect(requests).toBe(2);
    } finally {await page.goto('about:blank'); await new Promise<void>(done => server.close(() => done()));}
});
