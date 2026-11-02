import assert from 'node:assert/strict';
import {test} from 'node:test';
import {encode} from 'cbor-x';
import {createClient,WebSocketConnection} from '../dist/index.js';
class Socket {
 readyState=0;binaryType='';sent=[];onopen=null;onclose=null;onerror=null;onmessage=null;
 constructor(url){this.url=url;}
 send(value){this.sent.push(value);}
 close(){this.readyState=3;}
 open(){this.readyState=1;this.onopen?.({});}
 packet(value){const encoded=encode(value);this.onmessage?.({data:encoded.buffer.slice(encoded.byteOffset,encoded.byteOffset+encoded.byteLength)});}
}

for (const event of ['error','state-change']) test(`disconnect during ${event} prevents a retry`,async()=>{
 let attempts=0;
 const connection=new WebSocketConnection({url:'ws://server.invalid',reconnectDelay:1,
  socketFactory:()=>{attempts++;throw Error('offline');}});
 connection.on(event,value=>{if(event==='error'||value==='RECONNECTING') connection.disconnect();});
 connection.connect();await new Promise(resolve=>setTimeout(resolve,20));
 assert.equal(attempts,1);assert.equal(connection.getState(),'DISCONNECTED');connection.disconnect();
});
test('standalone client has no window dependency and exposes bidirectional socket traffic',()=>{
 assert.equal(typeof globalThis.window,'undefined');let socket;
 const client=createClient({baseUrl:'https://server.invalid/prefix',socketFactory:url=>(socket=new Socket(url))});
 const states=[];client.stream.subscribeToAppState(state=>states.push(state));
 client.stream.connect();socket.open();
 assert.equal(socket.url.protocol,'wss:');assert.equal(socket.url.pathname,'/prefix/websocket/connect');
 assert.ok(socket.url.searchParams.get('connection_id'));
 client.stream.sendDisplayFeedback(3,{cam:{width:640,height:480}});
 assert.deepEqual(JSON.parse(socket.sent.at(-1)),{frameNumber:3,displayImageSizes:{cam:{width:640,height:480}}});
 socket.onmessage({data:'ping'});assert.equal(socket.sent.at(-1),'pong');
 socket.packet({kind:'app_state',version:0,timestamp:0,sequence:0,server_pid:17,state:{camera_groups:{},realtime_pipelines:[]}});
 assert.equal(states[0].server_pid,17);client.close();assert.equal(socket.onmessage,null);assert.equal(socket.readyState,3);
});
test('malformed known packets reach protocol-error subscribers, unknown versions do not',()=>{
 let socket;const client=createClient({baseUrl:'http://server.invalid',socketFactory:url=>(socket=new Socket(url))});
 const errors=[];const messages=[];client.stream.subscribeToProtocolErrors(e=>errors.push(e));client.stream.subscribeToMessages(m=>messages.push(m));
 client.stream.connect();socket.open();socket.packet({kind:'frame',version:0,timestamp:0,sequence:0});
 assert.equal(errors.length,1);assert.equal(messages.length,0);
 socket.packet({kind:'frame',version:99});assert.equal(errors.length,1);client.close();
});
test('heartbeat sends text ping and disconnect clears its timer',async()=>{
 let socket;const connection=new WebSocketConnection({url:'ws://server.invalid/websocket/connect',heartbeatInterval:5,socketFactory:url=>(socket=new Socket(url))});
 connection.connect();socket.open();await new Promise(resolve=>setTimeout(resolve,16));
 assert.ok(socket.sent.includes('ping'));connection.disconnect();const count=socket.sent.length;
 await new Promise(resolve=>setTimeout(resolve,16));assert.equal(socket.sent.length,count);
});
test('retired socket callbacks cannot deliver after a manual disconnect',()=>{
 let socket;const client=createClient({baseUrl:'http://server.invalid',socketFactory:url=>(socket=new Socket(url))});
 let messages=0;client.stream.subscribeToMessages(()=>messages++);client.stream.connect();socket.open();
 const old=socket.onmessage;client.close();old({data:new ArrayBuffer(0)});assert.equal(messages,0);
});
test('connects from pages without a secure context, where crypto.randomUUID is missing',()=>{
 const prototype=Object.getPrototypeOf(globalThis.crypto);const original=Object.getOwnPropertyDescriptor(prototype,'randomUUID');
 Object.defineProperty(prototype,'randomUUID',{value:undefined,configurable:true});
 try{
  let socket;const connection=new WebSocketConnection({url:'ws://192.168.1.20:8080/stream',socketFactory:url=>(socket=new Socket(url))});
  const errors=[];connection.on('error',error=>errors.push(error));
  connection.connect();socket.open();
  assert.match(socket.url.searchParams.get('connection_id'),/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(connection.getState(),'CONNECTED');assert.deepEqual(errors,[]);connection.disconnect();
 }finally{Object.defineProperty(prototype,'randomUUID',original);}
});
test('a socket that cannot be created is reported, then retried',()=>{
 const connection=new WebSocketConnection({url:'ws://server.invalid/stream',reconnectDelay:60000,socketFactory:()=>{throw new SyntaxError('bad socket URL');}});
 const errors=[];connection.on('error',error=>errors.push(error));
 connection.connect();
 assert.equal(errors[0]?.message,'bad socket URL');assert.equal(connection.getState(),'RECONNECTING');connection.disconnect();
});
