import {createClient} from '@freemocap/client';
import {PlaybackManifestSchema, decodeRecordingParquet} from '@freemocap/client/recording';
const [, , baseUrl, recordingId, parentDirectory] = process.argv;
if (!baseUrl || !recordingId) throw new Error('Usage: node examples/recording.mjs SERVER RECORDING_ID [PARENT_DIRECTORY]');
const client = createClient({baseUrl});
const input = {path: {recording_id: recordingId}, query: {recording_parent_directory: parentDirectory}};
try {
    const manifest = PlaybackManifestSchema.parse((await client.operations.recordings_get_playback_manifest(input)).data);
    const {data: response} = await client.operations.recordings_get_recording_parquet(input);
    const runs = await decodeRecordingParquet(await response.arrayBuffer(), manifest);
    console.log(JSON.stringify({recording: manifest.recording_id, revision: manifest.revision,
        runs: Object.fromEntries(Object.entries(runs).map(([id, channels]) => [id, channels.map(item => ({
            kind: item.channel.kind, source: item.channel.source, stage: item.channel.stage,
            names: item.channel.names.length, components: Object.keys(item.channel.components), frames: item.frame_numbers.length,
        }))]))}, null, 2));
} finally {client.close();}
