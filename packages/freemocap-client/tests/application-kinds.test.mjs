import assert from 'node:assert/strict';
import {test} from 'node:test';
import {encode} from 'cbor-x';
import {z} from 'zod';
import {TransportService, ownByteStrings} from '@freemocap/client/stream';

class Socket {
 readyState=0;binaryType='';sent=[];onopen=null;onclose=null;onerror=null;onmessage=null;
 constructor(url){this.url=url;}
 send(value){this.sent.push(value);}
 close(){this.readyState=3;}
 open(){this.readyState=1;this.onopen?.({});}
 packet(value){const encoded=encode(value);this.onmessage?.({data:encoded.buffer.slice(encoded.byteOffset,encoded.byteOffset+encoded.byteLength)});}
}

// A robot's own state message, described the way an application would: a Zod schema.
const RobotState = z.object({kind:z.literal('robot_state'),version:z.literal(0),timestamp:z.number(),sequence:z.number().int(),
 servos:z.record(z.string(),z.number()),snapshot:z.instanceof(Uint8Array).optional()});
const envelope = {version:0,timestamp:1.5,sequence:3};

test('registrations preserve parser/version and reserved kinds after caller mutation',()=>{
 const definition={version:0,parse:message=>message};
 const kinds={robot_state:definition};const {stream,socket,errors}=robotStream(kinds);
 const values=[];const states=[];
 stream.subscribeToKind('robot_state',value=>values.push(value));
 stream.subscribeToAppState(value=>states.push(value));
 definition.version=4;definition.parse=()=>{throw Error('replacement');};
 kinds.app_state=definition;delete kinds.robot_state;
 socket.packet({kind:'robot_state',...envelope,servos:{}});
 socket.packet({kind:'app_state',...envelope,server_pid:17,state:{camera_groups:{},realtime_pipelines:[]}});
 assert.equal(values.length,1);assert.equal(states.length,1);assert.deepEqual(errors,[]);
 stream.disconnect();
});

test('invalid registration names, parsers and versions fail before connecting',()=>{
 for(const kinds of [{'':RobotState},{x:{}},{x:{parse:x=>x,version:-1}},{x:{parse:x=>x,version:0.5}}]){
  assert.throws(()=>new TransportService({url:'ws://robot.invalid',kinds}));
 }
});

test('public byte ownership survives mutation and transfer of ArrayBuffer inputs',()=>{
 const source=new Uint8Array([1,2,3]);const owned=ownByteStrings({nested:[source.buffer]});
 source.fill(9);structuredClone(source.buffer,{transfer:[source.buffer]});
 assert.deepEqual([...owned.nested[0]],[1,2,3]);
});

function robotStream(kinds={robot_state:RobotState}){
 let socket;const stream=new TransportService({url:'ws://robot.invalid/ws',socketFactory:url=>(socket=new Socket(url)),kinds});
 const errors=[];stream.subscribeToProtocolErrors(error=>errors.push(error));
 stream.connect();socket.open();
 return {stream,socket,errors};
}

test('generic channel subscription delivers one self-contained frame and clears on disconnect',()=>{
 const {stream,socket,errors}=robotStream();const received=[];
 stream.subscribeToChannels(frame=>received.push(frame));
 socket.packet({kind:'frame',...envelope,frame_number:3,model_sequence:0,
  convention:{units:'mm',handedness:'right',up_axis:'+z',forward_axis:'+y',rotation_frame:'local',rotation_form:'quaternion'},
  cameras:[],models:[],instances:[],trackers:[{tracker_id:'robot',detector_type:'test',model_id:null,
   channels:[{kind:'robot.signal',columns:['value'],names:['motor'],data:new Uint8Array([0,0,128,63])}]}]});
 assert.equal(received[0].channels[0].data[0],1);assert.equal(received[0].timestamp,1.5);
 assert.deepEqual(errors,[]);stream.disconnect();assert.equal(received.at(-1),null);
});

test('an application kind is validated and delivered to its own subscribers, not to FreeMoCap ones',()=>{
 const {stream,socket,errors}=robotStream();
 assert.equal(socket.url.pathname,'/ws');
 const states=[];const freemocap=[];
 stream.subscribeToKind('robot_state',state=>states.push(state));stream.subscribeToMessages(message=>freemocap.push(message));
 socket.packet({kind:'robot_state',...envelope,servos:{pan:90,tilt:12.5}});
 assert.deepEqual(states,[{kind:'robot_state',...envelope,servos:{pan:90,tilt:12.5}}]);
 assert.deepEqual(freemocap,[]);assert.deepEqual(errors,[]);
 stream.disconnect();
});

test('byte strings in application messages are owned copies, never views over the packet',()=>{
 const {stream,socket}=robotStream();const states=[];stream.subscribeToKind('robot_state',state=>states.push(state));
 socket.packet({kind:'robot_state',...envelope,servos:{},snapshot:new Uint8Array([7,8,9])});
 const {snapshot}=states[0];
 assert.deepEqual([...snapshot],[7,8,9]);assert.equal(snapshot.byteOffset,0);assert.equal(snapshot.buffer.byteLength,3);
 stream.disconnect();
});

test('unregistered kinds and unsupported versions are skipped; malformed registered messages are protocol errors',()=>{
 const {stream,socket,errors}=robotStream();const states=[];stream.subscribeToKind('robot_state',state=>states.push(state));
 socket.packet({kind:'telemetry',...envelope,anything:true});
 socket.packet({kind:'robot_state',...envelope,version:1,servos:{pan:1}});
 assert.deepEqual(states,[]);assert.equal(errors.length,0);
 socket.packet({kind:'robot_state',...envelope,timestamp:'late',servos:{}});
 socket.packet({kind:'robot_state',...envelope,servos:{pan:'ninety'}});
 assert.deepEqual(states,[]);assert.equal(errors.length,2);
 stream.disconnect();
});

test('a kind can declare the version it reads and validate with any parser',()=>{
 const seen=[];const {stream,socket}=robotStream({jaw:{version:2,parse:message=>{seen.push(message.version);return {open:message.open===true};}}});
 const states=[];stream.subscribeToKind('jaw',state=>states.push(state));
 socket.packet({kind:'jaw',...envelope,open:true});socket.packet({kind:'jaw',...envelope,version:2,open:true});
 assert.deepEqual(seen,[2]);assert.deepEqual(states,[{open:true}]);
 stream.disconnect();
});

test('FreeMoCap kinds cannot be redefined and keep their own handling beside application kinds',()=>{
 assert.throws(()=>new TransportService({url:'ws://robot.invalid/ws',kinds:{frame:RobotState}}),/cannot be redefined/);
 const {stream,socket,errors}=robotStream();const states=[];stream.subscribeToAppState(state=>states.push(state));
 socket.packet({kind:'app_state',...envelope,server_pid:17,state:{camera_groups:{},realtime_pipelines:[]}});
 assert.equal(states[0].server_pid,17);assert.deepEqual(errors,[]);
 assert.throws(()=>stream.subscribeToKind('telemetry',()=>{}),/not registered/);
 stream.disconnect();
});
