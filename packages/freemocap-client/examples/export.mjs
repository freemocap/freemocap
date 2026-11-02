import {setTimeout as delay} from 'node:timers/promises';
import {createClient} from '@freemocap/client';
const [, , baseUrl, recordingId, parentDirectory] = process.argv;
if (!baseUrl || !recordingId) throw new Error('Usage: node examples/export.mjs SERVER RECORDING_ID [PARENT_DIRECTORY]');
const client = createClient({baseUrl});
const input = {path: {recording_id: recordingId}, query: {recording_parent_directory: parentDirectory}};
try {
    const {data: options} = await client.operations.get_export_options_freemocap_recordings__recording_id__export_options_get(input);
    const {data: accepted} = await client.operations.create_export_freemocap_recordings__recording_id__exports_post({...input,
        body: {kind: 'channels', formats: ['npz'], data: ['LANDMARKS_3D'], run_id: options.selected_run_id, expected_revision: options.revision}});
    const deadline = Date.now() + 120000;
    let task;
    do {
        task = (await client.operations.get_task_freemocap_tasks__task_id__get({path: {task_id: accepted.task_id}, signal: AbortSignal.timeout(10000)})).data;
        if (['complete', 'failed', 'cancelled'].includes(task.status)) break;
        if (Date.now() > deadline) throw new Error(`Polling ended; server task ${accepted.task_id} may still be running`);
        await delay(250);
    } while (true);
    if (task.status !== 'complete') throw new Error(JSON.stringify(task));
    const {data: catalog} = await client.operations.list_exports_freemocap_recordings__recording_id__exports_get(input);
    console.log(JSON.stringify({task, catalog}, null, 2));
} finally {client.close();}
