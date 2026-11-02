import {setTimeout as delay} from 'node:timers/promises';
import {createClient} from '@freemocap/client';
const client = createClient({baseUrl: process.argv[2] ?? 'http://127.0.0.1:8005'});
const seconds = Number(process.argv[3] ?? 10);
if (!(seconds > 0 && seconds <= 300)) throw new Error('Duration must be 1–300 seconds');
let frames = 0;
const kinds = new Set(), errors = [];
client.stream.subscribeToMessages(message => {kinds.add(message.kind); if (message.kind === 'frame') frames++;});
client.stream.subscribeToModels(models => console.log(JSON.stringify({models: models.map(model => model.model_id)})));
client.stream.subscribeToProtocolErrors(error => errors.push(String(error)));
// Resolved frame consumers can use subscribeToModelFrames; copy arrays before mutation.
try {
    client.stream.connect();
    await delay(seconds * 1000);
    if (errors.length) throw new Error(errors.join('\n'));
    console.log(JSON.stringify({messageKinds: [...kinds], frames}));
} finally {client.close();}
