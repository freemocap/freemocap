import {createClient} from '@freemocap/client';
const client = createClient({baseUrl: process.argv[2] ?? 'http://127.0.0.1:8005'});
try {
    const {data: health} = await client.operations.healthcheck_endpoint_health_get();
    const {data: tasks} = await client.operations.all_tasks_freemocap_tasks_get();
    console.log(JSON.stringify({health, serverInstance: tasks.server_instance_id, tasks: tasks.tasks}, null, 2));
} finally {client.close();}
