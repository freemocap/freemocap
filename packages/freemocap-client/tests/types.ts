import {createClient, type ApiResult} from '../src/index.js';
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
