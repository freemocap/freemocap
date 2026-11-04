import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {readImagePayload, IMAGE_PAYLOAD_HEADER_SIZE, IMAGE_FRAME_HEADER_SIZE} from '../dist/images/index.js';
import * as root from '../dist/index.js';

// Encoded by SkellyCam's encode_image_payload (tools/generate-image-payload-fixture.py).
const fixture = JSON.parse(readFileSync(new URL('./fixtures/image-payload.json', import.meta.url), 'utf8'));
const encoded = Buffer.from(fixture.payload_base64, 'base64');
const payloadBuffer = () => encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);
// Authored from the generator's request, independently of the reader.
const expected = [
 {cameraId:'oak',cameraIndex:0,frameNumber:41,width:16,height:8,colorChannels:3},
 {cameraId:'zed-left',cameraIndex:3,frameNumber:41,width:8,height:8,colorChannels:3},
];
const withoutJpeg = ({jpeg,...image}) => image;
const secondCameraOffset = buffer => IMAGE_PAYLOAD_HEADER_SIZE + IMAGE_FRAME_HEADER_SIZE + new DataView(buffer).getInt32(IMAGE_PAYLOAD_HEADER_SIZE + 48, true);

test('rejects imprecise frame identities and invalid camera metadata',()=>{
 for(const edit of [
  view=>view.setBigInt64(8,9007199254740992n,true),
  view=>view.setUint8(IMAGE_PAYLOAD_HEADER_SIZE+16,255),
  view=>view.setInt32(IMAGE_PAYLOAD_HEADER_SIZE+32,-1,true),
  view=>view.setInt32(IMAGE_PAYLOAD_HEADER_SIZE+36,0,true),
  view=>view.setInt32(IMAGE_PAYLOAD_HEADER_SIZE+40,0,true),
  view=>view.setInt32(IMAGE_PAYLOAD_HEADER_SIZE+44,0,true),
 ]) {const buffer=payloadBuffer();edit(new DataView(buffer));assert.throws(()=>readImagePayload(buffer));}
});

test('reads every camera SkellyCam encoded, with JPEG views over the payload',()=>{
 const buffer = payloadBuffer();
 const payload = readImagePayload(buffer);
 assert.equal(payload.frameNumber, 41);
 assert.deepEqual(payload.images.map(withoutJpeg), expected);
 for (const {jpeg} of payload.images) {
  assert.equal(jpeg.buffer, buffer);
  assert.deepEqual([jpeg[0], jpeg[1], jpeg.at(-2), jpeg.at(-1)], [0xff, 0xd8, 0xff, 0xd9]);
 }
});

test('reads a payload held in a Uint8Array view at any offset',()=>{
 const padded = new Uint8Array(encoded.byteLength + 9); padded.set(encoded, 5);
 const payload = readImagePayload(padded.subarray(5, 5 + encoded.byteLength));
 assert.deepEqual(payload.images.map(withoutJpeg), expected);
 assert.equal(payload.images[0].jpeg.buffer, padded.buffer);
});

test('rejects malformed payloads instead of rendering part of them',()=>{
 const corrupt = (edit) => {const buffer = payloadBuffer(); edit(new DataView(buffer), buffer); return buffer;};
 assert.throws(()=>readImagePayload(payloadBuffer().slice(0, -1)), /truncated/);
 assert.throws(()=>readImagePayload(new Uint8Array([...encoded, 0])), /trailing/);
 assert.throws(()=>readImagePayload(corrupt(view => view.setUint8(0, 1))), /payload header/);
 assert.throws(()=>readImagePayload(corrupt(view => view.setInt32(16, 0, true))), /declares 0 cameras/);
 assert.throws(()=>readImagePayload(corrupt((view, buffer) => view.setBigInt64(buffer.byteLength - 16, 40n, true))), /footer/);
 assert.throws(()=>readImagePayload(corrupt((view, buffer) => view.setBigInt64(secondCameraOffset(buffer) + 8, 40n, true))), /frame 40, not 41/);
 assert.throws(()=>readImagePayload(corrupt((view, buffer) => {
  const id = secondCameraOffset(buffer) + 16; new Uint8Array(buffer).fill(0, id, id + 16); new Uint8Array(buffer).set([111, 97, 107], id);
 })), /repeats a camera/);
});

test('the package root exposes image reading and browser decoders without needing browser APIs to import',()=>{
 assert.equal(root.readImagePayload, readImagePayload);
 for (const name of ['decodeJpegBitmap','decodeJpegRgba','decodeImageBitmaps','decodeImagePixels']) assert.equal(typeof root[name], 'function');
});
