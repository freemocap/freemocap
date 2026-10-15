// Run from freemocap-ui: node --test electron/main/services/vscode.test.cjs
// Bundles in memory; no generated files or real application launches.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const vm = require('node:vm');
const {transformSync} = require('esbuild');
const {readFileSync} = require('node:fs');

const code = transformSync(readFileSync(path.join(__dirname, 'vscode.ts'), 'utf8'),
    {loader: 'ts', platform: 'node', format: 'cjs'}).code;

function fixture({handler = 'Visual Studio Code', failLaunch = false, download = false, directory = true} = {}) {
    const opened = [], dialogs = [];
    const electron = {
        app: {getApplicationNameForProtocol: () => handler},
        shell: {openExternal: async url => {
            opened.push(url);
            if (failLaunch && url.startsWith('vscode:')) throw new Error('Handler failed');
        }},
        dialog: {showMessageBox: async options => {dialogs.push(options); return {response: download ? 1 : 0};}},
    };
    const module = {exports: {}};
    vm.runInNewContext(code, {module, exports: module.exports, process,
        require: name => name === 'electron' ? electron : name === 'node:fs/promises'
            ? {stat: async () => ({isDirectory: () => directory})} : require(name)});
    return {service: module.exports, opened, dialogs};
}

test('folder URLs round-trip special characters without query or fragment injection', () => {
    const {service} = fixture();
    const folder = path.resolve('recordings', 'trial #1 ? café & 100%');
    const url = new URL(service.vscodeFolderURL(folder));
    assert.equal(url.protocol, 'vscode:');
    assert.equal(url.hostname, 'file');
    assert.equal(url.search, '');
    assert.equal(url.hash, '');
    assert.ok(decodeURIComponent(url.pathname).endsWith('/trial #1 ? café & 100%'));
    assert.throws(() => service.vscodeFolderURL('relative/path'));
});

test('available handler opens the folder without a dialog', async () => {
    const {service, opened, dialogs} = fixture();
    assert.equal(service.isVSCodeAvailable(), true);
    assert.equal(await service.openFolderInVSCode(path.resolve('recordings')), true);
    assert.equal(opened.length, 1);
    assert.equal(dialogs.length, 0);
});

test('missing handler offers setup without launching', async () => {
    const {service, opened, dialogs} = fixture({handler: ''});
    assert.equal(service.isVSCodeAvailable(), false);
    assert.equal(await service.openFolderInVSCode(path.resolve('recordings')), false);
    assert.equal(opened.length, 0);
    assert.equal(dialogs.length, 1);
});

test('failed OS handoff offers download only when chosen', async () => {
    const {service, opened, dialogs} = fixture({failLaunch: true, download: true});
    assert.equal(await service.openFolderInVSCode(path.resolve('recordings')), false);
    assert.equal(dialogs.length, 1);
    assert.equal(opened[1], 'https://code.visualstudio.com/download');
});

test('non-directory paths are rejected before OS handoff', async () => {
    const {service, opened, dialogs} = fixture({directory: false});
    assert.equal(await service.openFolderInVSCode(path.resolve('file.txt')), false);
    assert.equal(opened.length, 0);
    assert.equal(dialogs.length, 1);
});

test('Windows UNC host survives URL encoding', {skip: process.platform !== 'win32'}, () => {
    const {service} = fixture();
    assert.equal(service.vscodeFolderURL('\\\\server\\share\\trial #1'), 'vscode://file//server/share/trial%20%231');
});
