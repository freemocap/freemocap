/** Canonical server-encoded recorded channels over a real loopback WebSocket. */
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {setTimeout as delay} from 'node:timers/promises';
import {createClient} from '../dist/index.js';
const config = JSON.parse(await readFile(process.argv[2], 'utf8'));
const results = [];
for (const [index, reference] of config.recordings.entries()) {
    const expected = JSON.parse(await readFile(reference.expected, 'utf8'));
    const stride = expected.channel.names.length * Object.keys(expected.channel.components).length;
    const client = createClient({baseUrl: `${config.url}/${index}`});
    const errors = [];
    let received = 0, resolved = 0, modelNotifications = 0, currentSlot = 0;
    let firstModel, previousConnectionModel, retained, retainedCopy;
    const guard = callback => value => {try {callback(value);} catch (error) {errors.push(String(error.stack));}};
    client.stream.subscribeToProtocolErrors(error => errors.push(String(error)));
    client.stream.subscribeToModels(models => {if (models.length) modelNotifications++;});
    client.stream.subscribeToMessages(guard(message => {
        if (message.kind !== 'frame') return;
        currentSlot = expected.frames.indexOf(message.frame_number);
        received++;
        assert.ok(currentSlot >= 0);
        assert.equal(message.timestamp, expected.times[currentSlot]);
        if (firstModel) assert.equal(message.models[0], firstModel, 'repeated model metadata keeps identity');
        else {firstModel = message.models[0]; assert.notEqual(firstModel, previousConnectionModel, 'new connection owns its metadata cache');}
    }));
    client.stream.subscribeToModelFrames(guard(models => {
        if (!models.length) return; // Disconnect/reset deliberately clears subscribers.
        resolved++;
        const points = models[0].landmarks;
        assert.deepEqual(points.names, expected.channel.names);
        assert.equal(points.data.length, stride);
        for (let component = 0; component < stride; component++) {
            const value = expected.values[currentSlot * stride + component];
            if (value === null) assert.ok(Number.isNaN(points.data[component]));
            else assert.equal(points.data[component], Math.fround(value));
        }
        if (!retained) {retained = points.data; retainedCopy = points.data.slice();}
    }));
    try {
        for (const start of [0, 37]) {
            received = 0; resolved = 0; modelNotifications = 0; firstModel = undefined;
            retained = undefined; retainedCopy = undefined;
            client.stream.updateUrl(`${config.url.replace('http:', 'ws:')}/${index}/websocket/connect?start=${start}`);
            client.stream.connect();
            const deadline = Date.now() + 60000;
            while (resolved < expected.frames.length - start) {
                assert.ok(Date.now() < deadline, `replay timed out: ${resolved} frames; ${errors.join(' | ')}`);
                await delay(10);
            }
            assert.deepEqual(errors, []);
            assert.equal(received, expected.frames.length - start);
            assert.equal(modelNotifications, 1);
            assert.deepEqual(retained, retainedCopy, 'later packets do not overwrite retained numerical data');
            client.stream.sendDisplayFeedback(expected.frames.at(-1), {});
            await delay(30);
            previousConnectionModel = firstModel;
            client.stream.disconnect();
            results.push({recording: reference.id, startFrame: expected.frames[start], frames: received,
                comparedValues: received * stride, modelNotifications, retainedDataUnchanged: true});
        }
    } finally {client.close();}
}
await writeFile(config.report, JSON.stringify({results}, null, 2) + '\n');
console.log(JSON.stringify({results}));
