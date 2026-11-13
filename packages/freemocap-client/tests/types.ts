import {createClient, TransportService, type ApiResult} from '../src/index.js';
function check(client:ReturnType<typeof createClient>){
 client.operations.describe_recording_freemocap_recordings__recording_id__get({path:{recording_id:'trial'}});
 // @ts-expect-error recording identity is required
 client.operations.describe_recording_freemocap_recordings__recording_id__get();
 // @ts-expect-error invented operation is not supported
 client.operations.launchServer();
 // @ts-expect-error run ID is numeric, not an arbitrary string
 client.operations.list_run_channels_freemocap_recordings__recording_id__runs__run_id__channels_get({path:{recording_id:'trial',run_id:'bad'}});
 const asset:Promise<ApiResult<Response>>=client.operations.recordings_stream_video({path:{recording_id:'trial',video_id:'cam.mp4'}});
 // @ts-expect-error pause requires boolean, not a string
 client.operations.pause_camera_groups_skellycam_camera_group_all_pause_put({body:{paused:'true'}});
 client.operations.pause_camera_groups_skellycam_camera_group_all_pause_put({body:{paused:false}});
 void asset;
}
void check;
function checkApplicationKinds(client:ReturnType<typeof createClient>){
 const stream=new TransportService({url:'ws://robot.invalid/ws',kinds:{robot_state:{parse:(message:unknown)=>message as {servos:Record<string,number>}}}});
 stream.subscribeToKind('robot_state',state=>{const pan:number|undefined=state.servos.pan;void pan;});
 // @ts-expect-error only registered kinds can be subscribed
 stream.subscribeToKind('telemetry',()=>{});
 // @ts-expect-error a FreeMoCap client registers no application kinds
 client.stream.subscribeToKind('robot_state',()=>{});
}
void checkApplicationKinds;

function checkGenericChannels(stream:TransportService){
 stream.subscribeToChannels(frame=>{
  if(!frame)return;
  for(const channel of frame.channels){
   const values:Float32Array=channel.data;void values;
   if(channel.owner.scope==='tracker'){
    const id:string=channel.owner.trackerId;void id;
    // @ts-expect-error tracker channels do not invent reconstructed instance identities
    channel.owner.instanceId;
   }
  }
 });
}
void checkGenericChannels;
