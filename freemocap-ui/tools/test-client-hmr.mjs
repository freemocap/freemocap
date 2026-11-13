import assert from 'node:assert/strict';
import {mkdir, mkdtemp, writeFile, rm} from 'node:fs/promises';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {createServer, normalizePath} from 'vite';
import {clientAliases, clientRoot} from './local-client.mjs';

// Scratch files live in the repository's ignored .test-artifacts directory.
const scratchRoot = path.join(clientRoot, '.test-artifacts');
await mkdir(scratchRoot, {recursive: true});
const scratch = await mkdtemp(path.join(scratchRoot, 'hmr-'));
const probe = path.join(scratch, 'probe.ts');
const url = `/@fs/${normalizePath(probe)}`;
const server = await createServer({
    configFile: false,
    resolve: {alias: clientAliases},
    optimizeDeps: {exclude: ['@freemocap/client'], noDiscovery: true},
    server: {host: '127.0.0.1', port: 0, preTransformRequests: false, fs: {allow: [process.cwd(), clientRoot]}},
});
try {
    await writeFile(probe, 'export const version = "before"; import.meta.hot.accept();\n');
    await server.listen();
    for (const specifier of ['@freemocap/client', '@freemocap/client/http', '@freemocap/client/images', '@freemocap/client/recording']) {
        const {replacement} = clientAliases.find(alias => alias.find.test(specifier));
        const resolved = await server.pluginContainer.resolveId(specifier);
        assert.equal(normalizePath(resolved.id), normalizePath(replacement));
        const transformed = await server.transformRequest(`/@fs/${normalizePath(replacement)}`);
        assert.ok(transformed?.code, `${specifier} source transforms without dist`);
    }
    assert.match((await server.transformRequest(url)).code, /before/);
    const updates = [];
    const originalSend = server.ws.send.bind(server.ws);
    server.ws.send = (...args) => { updates.push(args[0]); return originalSend(...args); };
    await writeFile(probe, 'export const version = "after"; import.meta.hot.accept();\n');
    const deadline = Date.now() + 10000;
    while (!updates.some(message => message.type === 'update') && Date.now() < deadline) await delay(25);
    assert.ok(updates.some(message => message.type === 'update' &&
        message.updates.some(update => update.path === url)), 'client edit emits an HMR update');
    assert.match((await server.transformRequest(url)).code, /after/);
    console.log('All client exports resolve to source; client edits emit HMR and serve fresh code.');
} finally {
    await server.close();
    await rm(scratch, {recursive: true, force: true});
}
