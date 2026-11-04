import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {encode} from 'cbor-x';

const bundle = new URL('../dist/browser/freemocap-client.js', import.meta.url);
const source = readFileSync(bundle, 'utf8');

test('the browser bundle is one module with nothing left to resolve',()=>{
 // Statements only: operation paths such as "/freemocap/dlc/import" also end in import".
 assert.doesNotMatch(source, /(?:^|[;}\n])\s*import\s*(?:[\w$*{}\s,]+from\s*)?["']/);
 assert.doesNotMatch(source, /\bimport\s*\(/);
 assert.doesNotMatch(source, /\brequire\s*\(/);
});

test('the browser bundle decodes stream messages and image payloads by itself',async()=>{
 const sdk = await import(bundle.href);
 const message = sdk.decodeMessage(encode({kind:'app_state',version:0,timestamp:0,sequence:0,server_pid:17,state:{camera_groups:{},realtime_pipelines:[]}}));
 assert.equal(message.server_pid, 17);
 const fixture = JSON.parse(readFileSync(new URL('./fixtures/image-payload.json', import.meta.url), 'utf8'));
 const payload = sdk.readImagePayload(Buffer.from(fixture.payload_base64, 'base64'));
 assert.deepEqual(payload.images.map(image => image.cameraId), ['oak', 'zed-left']);
});
