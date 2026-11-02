import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {TransportService, OverlayLayer, readImagePayload} from '../dist/index.js';

// Encoded by the freemocap-stream Python package (tools/generate-python-stream-fixture.py).
const fixture = JSON.parse(readFileSync(new URL('./fixtures/python-stream.json', import.meta.url), 'utf8'));
const packet = base64 => {const bytes = Buffer.from(base64, 'base64'); return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);};

test('frames and application messages from the Python package resolve through TransportService',()=>{
 let socket;
 const stream = new TransportService({url:'ws://robot.invalid/ws',kinds:{robot_state:{parse:message=>message}},
  socketFactory:url=>(socket={url,readyState:0,send(){},close(){this.readyState=3;}})});
 const overlays=[],images=[],cameras=[],states=[],errors=[];
 stream.subscribeToOverlay(overlay=>overlays.push(overlay));
 stream.subscribeToImages((buffer,frameNumber)=>images.push({buffer,frameNumber}));
 stream.subscribeToCameras(update=>cameras.push(update));
 stream.subscribeToKind('robot_state',state=>states.push(state));
 stream.subscribeToProtocolErrors(error=>errors.push(error));
 stream.connect();socket.readyState=1;socket.onopen?.({});
 socket.onmessage({data:packet(fixture.frame_base64)});socket.onmessage({data:packet(fixture.robot_state_base64)});
 stream.disconnect();

 assert.deepEqual(errors,[]);
 assert.equal(overlays.length,1);
 const [overlay]=overlays;
 assert.equal(overlay.cameraId,'oak');assert.equal(overlay.layer,OverlayLayer.DETECTIONS);assert.equal(overlay.frameNumber,41);
 assert.deepEqual(overlay.names,['nose','left_eye','right_eye']);assert.deepEqual(overlay.columns,['x','y','visibility']);
 assert.deepEqual(overlay.imageSize,[64,48]);
 const values=[...overlay.data];
 assert.deepEqual(values.slice(0,4),[32.5,20.25,Math.fround(0.9),30]);assert.ok(Number.isNaN(values[5]));
 assert.deepEqual(overlay.connectionGroups,[{name:'face',pairs:[['nose','left_eye'],['nose','right_eye']],color:'#00e5a0'}]);
 assert.equal(cameras[0][0].match_kind,'unmatched');assert.deepEqual(cameras[0][0].image_size,[64,48]);
 assert.equal(images[0].frameNumber,41);
 assert.deepEqual(readImagePayload(images[0].buffer).images.map(({cameraId,width,height})=>[cameraId,width,height]),[['oak',64,48]]);
 assert.deepEqual(states,[{kind:'robot_state',version:0,timestamp:10.3,sequence:7,servos:{pan:90,tilt:12.5}}]);
});
