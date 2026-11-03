import assert from 'node:assert/strict';
import {test} from 'node:test';
import {encode} from 'cbor-x';
import {MessageDecoder, decodeMessage} from '../dist/index.js';
import {FrameResolver, resolveChannelViews} from '../dist/index.js';
import type {FrameMessage} from '../dist/index.js';

// Contract trace: shared/server-contract/README.md. Hand-authored IEEE754 bytes:
// 1.0 = 00 00 80 3f, 2.0 = 00 00 00 40, 3.0 = 00 00 40 40.
const coordinates = () => new Uint8Array([0,0,128,63,0,0,0,64,0,0,64,64]);
function frame(): object {
 return {kind:'frame',version:0,timestamp:12.5,sequence:9,frame_number:9,model_sequence:0,
  convention:{units:'mm',handedness:'right',up_axis:'+z',forward_axis:'+y',rotation_frame:'local',rotation_form:'quaternion'},
  cameras:[],models:[{model_id:'tool',segments:[],landmarks:[{name:'opaque-name'}],connections:[],scale_reference_name:'edge_length'}],
  instances:[{instance_id:7,model_id:'tool',fitted_scale_mm:null,channels:[{kind:'LANDMARKS_3D',columns:['z','x','y'],data:coordinates()}]}],
  trackers:[],image:new Uint8Array([255,216,255,217])};
}
function decoded(decoder:MessageDecoder, raw:object):FrameMessage {
 const value=decoder.decode(encode(raw));assert.ok(value?.kind==='frame');return value;
}

test('generic views retain custom channels, owner identity and unnamed rows without inventing semantics',()=>{
 const raw=frame() as any;
 raw.trackers=[{tracker_id:'robot-a',detector_type:'robot',model_id:null,channels:[
  {kind:'robot.temperature',columns:['celsius','quality','extra'],names:['motor'],data:coordinates(),sample_status:new Uint8Array([1]),status_labels:['missing','measured']},
 ]}];
 raw.instances[0].channels.push({kind:'robot.custom',columns:['value'],data:coordinates()});
 const value=decoded(new MessageDecoder(),raw);const result=resolveChannelViews(value);
 assert.equal(result.timestamp,12.5);assert.equal(result.frameNumber,9);
 assert.deepEqual(result.channels[0].owner,{scope:'tracker',trackerId:'robot-a',modelId:null});
 assert.deepEqual([...result.channels[0].data],[1,2,3]);
 assert.equal(result.channels[0].descriptor,value.trackers[0].channels[0]);
 assert.equal(result.channels[0].data.buffer,value.trackers[0].channels[0].data.buffer);
 assert.deepEqual(result.channels[2].owner,{scope:'instance',instanceId:7,modelId:'tool'});
 assert.equal(result.channels[2].descriptor.names,undefined);assert.equal(result.channels[2].rowCount,3);
 const later=decoded(new MessageDecoder(),{...raw,trackers:[]});resolveChannelViews(later);
 assert.deepEqual([...result.channels[0].data],[1,2,3]);
});

test('generic views reject inconsistent row descriptions rather than silently reshaping data',()=>{
 for(const extra of [{columns:['v','v','v']},{columns:['a','b']},{names:['a','b']},{sample_status:new Uint8Array(2)}]){
  const raw=frame() as any;raw.instances[0].channels=[{kind:'robot.custom',columns:['x','y','z'],data:coordinates(),...extra}];
  assert.throws(()=>resolveChannelViews(decoded(new MessageDecoder(),raw)));
 }
});

test('overlays preserve detector and reconstructed instance identities',()=>{
 const raw=frame() as any;
 raw.trackers=['first','second'].map(tracker_id=>({tracker_id,detector_type:'pose',model_id:null,channels:[
  {kind:'OVERLAY_2D',camera_id:'camera',names:['point'],columns:['x','y','visibility'],data:coordinates()},
 ]}));
 raw.instances[0].channels=[{kind:'OVERLAY_REPROJECTIONS',camera_id:'camera',columns:['x','y','visibility'],data:new Uint8Array(0)}];
 const result=new FrameResolver().resolve(decoded(new MessageDecoder(),raw));
 assert.deepEqual(result.overlays.map(o=>o.trackerId),['first','second',undefined]);
 assert.equal(result.overlays[2].instanceId,7);assert.equal(result.overlays[2].modelId,'tool');
});
test('one complete frame resolves without previous messages or a human-specific model',()=>{
 const value=decoded(new MessageDecoder(),frame()); const resolved=new FrameResolver().resolve(value);
 assert.equal(value.timestamp,12.5);assert.equal(value.instances[0].fitted_scale_mm,null);
 assert.equal(resolved.models[0].instanceId,7);const points=resolved.models[0].landmarks!;
 assert.deepEqual(points.names,['opaque-name']);assert.deepEqual([...points.data],[1,2,3]);
 assert.deepEqual(points.coordinateOffsets,[1,2,0]); // x=2,y=3,z=1 from declared columns.
});
test('separate models resolve their own identity tables rather than the first model',()=>{
 const raw=frame() as any;
 raw.models.push({...raw.models[0],model_id:'other',landmarks:[{name:'different'}]});
 raw.instances.push({...raw.instances[0],instance_id:23,model_id:'other'});
 const result=new FrameResolver().resolve(decoded(new MessageDecoder(),raw));
 assert.deepEqual(result.models.map(m=>[m.instanceId,m.landmarks!.names]),[[7,['opaque-name']],[23,['different']]]);
});
test('equal metadata reuses identity, changed content with equal IDs and counters replaces it',()=>{
 const decoder=new MessageDecoder();const first=decoded(decoder,frame());const same=decoded(decoder,frame());
 assert.equal(first.models,same.models);
 const changed=frame() as any;changed.models[0].landmarks[0].name='renamed';
 const next=decoded(decoder,changed);assert.notEqual(first.models,next.models);
 assert.equal(next.models[0].landmarks[0].name,'renamed');assert.equal(first.models[0].landmarks[0].name,'opaque-name');
});
test('later numerical packets never overwrite previously published bytes',()=>{
 const decoder=new MessageDecoder();const first=decoded(decoder,frame());
 const next=frame() as any;next.instances[0].channels[0].data=new Uint8Array(12);
 decoded(decoder,next);assert.deepEqual([...first.instances[0].channels[0].data],[...coordinates()]);
});
test('decoder owns incoming bytes and reset prevents stale metadata identity reuse',()=>{
 const decoder=new MessageDecoder();const packet=encode(frame());const first=decoder.decode(packet) as FrameMessage;
 packet.fill(0);assert.deepEqual([...first.instances[0].channels[0].data],[...coordinates()]);
 decoder.reset();const next=decoded(decoder,frame());assert.notEqual(first.models,next.models);
});
test('unknown versions and kinds are skipped but a known malformed frame fails',()=>{
 assert.equal(decodeMessage(encode({...frame(),version:999})),null);
 assert.equal(decodeMessage(encode({kind:'future',version:0})),null);
 assert.throws(()=>decodeMessage(encode({kind:'frame',version:0,timestamp:0,sequence:0})));
});
test('mismatched row bytes cannot silently become a different coordinate layout',()=>{
 const raw=frame() as any;raw.instances[0].channels[0].data=new Uint8Array(8);
 assert.throws(()=>new FrameResolver().resolve(decoded(new MessageDecoder(),raw)));
});
test('display-only held values are not fabricated as fresh observations',()=>{
 const resolver=new FrameResolver();resolver.resolve(decoded(new MessageDecoder(),frame()));
 const missing=frame() as any;missing.instances=[];
 assert.deepEqual(resolver.resolve(decoded(new MessageDecoder(),missing)).models,[]);
});

test('non-frame kinds decode without a frame or metadata handshake',()=>{
 const envelope={version:0,timestamp:0,sequence:0};
 const snapshot={server_instance_id:'00000000-0000-4000-8000-000000000001',revision:4,recording_owners:[],tasks:[]};
 const progress=decodeMessage(encode({...envelope,kind:'progress',snapshot}));
 assert.equal(progress?.kind,'progress');if(progress?.kind==='progress')assert.equal(progress.snapshot.revision,4);
 const state=decodeMessage(encode({...envelope,kind:'app_state',server_pid:123,state:{camera_groups:{},realtime_pipelines:[]}}));
 assert.equal(state?.kind,'app_state');
 const timing={mean_frame_duration_ms:20,mean_frames_per_second:50,frame_duration_max:20,frame_duration_min:20,
 frame_duration_mean:20,frame_duration_stddev:0,frame_duration_median:20,frame_duration_coefficient_of_variation:0,
 calculation_window_size:10,framerate_source:'capture'};
 assert.equal(decodeMessage(encode({...envelope,kind:'framerate',camera_group_id:'group',backend_framerate:timing,frontend_framerate:timing}))?.kind,'framerate');
 const record={name:'test',msg:'hello',args:[],levelname:'INFO',levelno:20,pathname:'test.py',filename:'test.py',module:'test',
 lineno:1,funcName:'fixture',created:1,msecs:0,relativeCreated:0,thread:1,threadName:'main',processName:'test',process:1,
 delta_t:'0',message:'hello',asctime:'fixture',formatted_message:'hello',type:'log'};
 assert.equal(decodeMessage(encode({...envelope,kind:'log',record}))?.kind,'log');
});

test('startup uses complete retained progress records after reconnect',()=>{
 const snapshots = [
  {task_type:'realtime_startup', result:{status:'ready',phase:'ready',pipeline_id:'live',preview_ready:true}},
 ];
 const packet=encode({kind:'progress',version:0,timestamp:0,sequence:0,snapshot:{
  server_instance_id:'00000000-0000-4000-8000-000000000001',revision:9,recording_owners:[],
  tasks:snapshots.map((entry,index)=>({...entry,task_id:`${entry.task_type}:generation`,revision:3,
   recording:null,status:index===0?'complete':'cancelled',progress:{phase:entry.result.phase,
   progress_fraction:null,detail:'Retained status'},cameras:[],
   created_at:'2026-11-02T20:00:00Z',updated_at:'2026-11-02T20:01:00Z'})),
 }});
 for(const decoder of [new MessageDecoder(),new MessageDecoder()]) {
  const message=decoder.decode(packet);assert.equal(message?.kind,'progress');
  if(message?.kind!=='progress')throw new Error('Expected progress');
  assert.deepEqual(message.snapshot.tasks.map(task=>task.result),snapshots.map(task=>task.result));
  assert.equal(message.snapshot.revision,9);
 }
});
