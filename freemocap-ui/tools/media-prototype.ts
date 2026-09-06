import {createServer} from 'vite';
import {build} from 'esbuild';
import {mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve, join} from 'node:path';
import {spawn} from 'node:child_process';
import electron from 'electron';

const server = await createServer({configFile: false, root: resolve('prototypes/media-decoder'),
    server: {host: '127.0.0.1', port: 0, fs: {allow: [process.cwd()]}}});
const temporary = await mkdtemp(join(tmpdir(), 'freemocap-media-'));
const entry = join(temporary, 'main.cjs');
await build({entryPoints: ['tools/media-electron.ts'], bundle: true, platform: 'node',
    format: 'cjs', external: ['electron'], outfile: entry});
await server.listen();
try {
    const url = server.resolvedUrls?.local[0];
    if (!url) throw new Error('Prototype server has no local URL');
    const environment = {...process.env};
    delete environment.ELECTRON_RUN_AS_NODE;
    const child = spawn(electron as unknown as string, [entry, url], {stdio: 'inherit', env: environment});
    const code = await new Promise<number | null>((resolveExit, reject) => {
        child.once('error', reject); child.once('exit', resolveExit);
    });
    if (code !== 0) throw new Error(`Prototype Electron exited with code ${code}`);
} finally { await server.close(); }
