import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import {OnnxPreparationView} from './OnnxPreparationView';
import {OnnxPreparationSchema, type OnnxPreparation} from '@/types/onnx-preparation';

const base: OnnxPreparation = {pipeline_id: 'p', status: 'idle', phase: 'awaiting_request', elapsed_seconds: 0,
    model_name: null, message: null, error: null, can_prepare: true, can_cancel: false,
    requested_provider: 'tensorrt', active_provider: 'cuda'};
const render = (patch: Partial<OnnxPreparation> = {}) => renderToStaticMarkup(<OnnxPreparationView snapshot={{...base, ...patch}} onPrepare={() => {}} onStop={() => {}}/>);

test('explicit preparation shows requested and actual providers without claiming activation', () => {
    const html = render();
    assert.match(html, /Requested provider: tensorrt/); assert.match(html, /Active provider: cuda/);
    assert.match(html, /Prepare TensorRT/); assert.match(html, /may reduce live FPS/);
    assert.doesNotMatch(html, /Stop preparation; keep CUDA/);
    assert.match(render({active_provider: null}), /Active provider: Not reported/);
    assert.match(render({requested_provider: null}), /Requested provider: Auto/);
});
test('preparation and cancellation capabilities control actions and stopping remains honest', () => {
    const running = render({status: 'running', can_prepare: false, can_cancel: true, elapsed_seconds: 187});
    assert.match(running, /3m 07s/); assert.match(running, /Stop preparation; keep CUDA/);
    assert.doesNotMatch(running, />Prepare TensorRT</);
    assert.match(render({status: 'stopping', can_prepare: false, can_cancel: true}), /Waiting for the preparation worker to exit and release its resources/);
    assert.match(render({status: 'failed', error: 'Model failed'}), /Retry TensorRT preparation/);
    assert.doesNotMatch(render({status: 'activated', can_prepare: false, can_cancel: true}), /Stop preparation; keep CUDA/);
});
test('unsupported preparation is nonblocking with no actions; invalid snapshots rejected', () => {
    const html = renderToStaticMarkup(<OnnxPreparationView snapshot={base} unavailable onPrepare={() => {}}/>);
    assert.match(html, /unavailable from this server version/); assert.doesNotMatch(html, /button|role="alert"/);
    assert.equal(OnnxPreparationSchema.safeParse({...base, elapsed_seconds: -1}).success, false);
});
