import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {decodeMessage} from './cbor-codec';
import {TransportService} from './TransportService';
import {ModelDefinitionSchema} from './message-contract';

test('frame contents replace stale definitions despite an unchanged model revision', () => {
    const message = decodeMessage(readFileSync('src/services/server/transport/__fixtures__/message_frame_golden.bin'));
    assert.ok(message?.kind === 'frame');
    const model = ModelDefinitionSchema.parse({model_id: 'tracked-object', segments: [], landmarks: [], connections: []});
    const frame = {...message, models: [model], instances: [], trackers: [], image: undefined};
    const service = new TransportService({url: 'ws://localhost/websocket/connect'});
    let updates = 0;
    service.subscribeToModels(() => {updates++;});
    service['handleFrame']({...frame, models: []});
    service['handleFrame'](frame);
    assert.ok(frame.models.length > 0);
    assert.equal(updates, 2);
    const retained = service.getModels();
    service['handleFrame'](structuredClone(frame));
    assert.equal(updates, 2);
    assert.equal(service.getModels(), retained);
    service['handleFrame']({...frame, models: []});
    assert.deepEqual(service.getModels(), []);
    assert.equal(updates, 3);
});
