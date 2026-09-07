import {test, _electron as electron} from '@playwright/test';
import {createServer} from 'vite';
import {build} from 'esbuild';
import {mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

test('measure JPEG decode throughput in Electron', async () => {
    test.setTimeout(120_000);
    const temporary = await mkdtemp(join(tmpdir(), 'jpeg-throughput-'));
    const server = await createServer({configFile: false, root: temporary, resolve: {alias: {'jpeg-js': resolve('node_modules/jpeg-js/index.js')}}, server: {host: '127.0.0.1', port: 0, watch: null, hmr: false, fs: {allow: [process.cwd(), temporary]}}});
    const entry = join(temporary, 'main.cjs');
    await build({entryPoints: ['tools/media-electron.ts'], bundle: true, platform: 'node', format: 'cjs', external: ['electron'], outfile: entry});
    await server.listen();
    try {
        const app = await electron.launch({args: [entry, server.resolvedUrls!.local[0]], env: {...process.env, MEDIA_TEST: '1'}});
        try {
            const page = await app.firstWindow();
            const measurements = await page.evaluate(async (workerUrl) => {
                const worker = new Worker(workerUrl, {type: 'module'});
                try {
                    return await new Promise((resolve, reject) => {
                        worker.onmessage = event => resolve(event.data);
                        worker.onerror = event => reject(new Error(event.message));
                        worker.postMessage(null);
                    });
                } finally {worker.terminate();}
            }, `/@fs/${resolve('tools/jpeg-benchmark.worker.ts').replaceAll('\\', '/')}`);
            console.log(JSON.stringify(measurements));
        } finally {await app.close();}
    } finally {await server.close();}
});
