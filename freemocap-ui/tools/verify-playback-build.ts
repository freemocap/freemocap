/** Compile the renderer and worker without launching Electron or modifying app build output. */
import {build} from 'vite';
import react from '@vitejs/plugin-react';
import {mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

const output = await mkdtemp(join(tmpdir(), 'freemocap-renderer-'));
await build({configFile: false, root: process.cwd(), resolve: {alias: {'@': resolve('src')}},
    plugins: [react({exclude: [/\.worker\.[jt]sx?$/]})], worker: {format: 'es'},
    build: {outDir: output, emptyOutDir: false}});
