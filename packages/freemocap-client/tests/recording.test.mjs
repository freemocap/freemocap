import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {decodeRecordingParquet,decodePlaybackParquet,PlaybackManifestSchema} from '../dist/recording/index.js';
const fixture=JSON.parse(readFileSync(new URL('./fixtures/generic-recording.json',import.meta.url),'utf8'));
const bytes=Buffer.from(fixture.parquet_base64,'base64');
const file=bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);
const manifest=PlaybackManifestSchema.parse(fixture.manifest);
test('generic recording reader preserves non-scene channels, declared order and native clocks',async()=>{
 const result=await decodeRecordingParquet(file,manifest);assert.equal(result[0].length,2);
 const eye=result[0][0],body=result[0][1];
 assert.equal(eye.channel.stage,'observations');assert.equal(body.channel.stage,'reconstruction');
 assert.equal(eye.channel.kind,'PUPIL_DIAMETER');assert.deepEqual(eye.frame_numbers,[10,11]);
 assert.deepEqual(eye.timestamps_s,[.100,.108]);assert.deepEqual(Array.from(eye.values),[3,2,4,NaN]);
 assert.ok(eye.values instanceof Float64Array);assert.deepEqual(body.frame_numbers,[2]);
 assert.deepEqual(body.timestamps_s,[1]);assert.deepEqual(Array.from(body.values),[3,1,2]);
 assert.deepEqual(Object.keys(body.channel.components),['z','x','y']);
});
test('application playback selection retains its existing scene-only allocation',async()=>{
 const result=await decodePlaybackParquet(file,manifest);assert.equal(result[0].length,1);
 assert.equal(result[0][0].channel.kind,'LANDMARKS_3D');assert.deepEqual(Array.from(result[0][0].values),[3,1,2]);
});
