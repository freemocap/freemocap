import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';

test('recording schemas and source exports load when startup forbids WASM compilation', () => {
    const entry = new URL('../dist/recording/index.js', import.meta.url).href;
    const result = spawnSync(process.execPath, ['--input-type=module', '-e', `
        const forbidden = () => { throw new Error('Startup must not compile WebAssembly'); };
        WebAssembly.Module = function () { forbidden(); };
        WebAssembly.compile = forbidden;
        WebAssembly.instantiate = forbidden;
        WebAssembly.compileStreaming = forbidden;
        WebAssembly.instantiateStreaming = forbidden;
        const recording = await import(${JSON.stringify(entry)});
        if (!recording.PlaybackManifestSchema || typeof recording.decodeRecordingParquet !== 'function') {
            throw new Error('Recording public API missing');
        }
    `], {encoding: 'utf8'});
    assert.equal(result.status, 0, result.stderr || String(result.error ?? ''));
});
