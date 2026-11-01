// Measurement harness around the production receiver/store; no alternate transport.
import {ViewportFrameReceiver} from '../src/components/viewport3d/viewport-frame-transfer';
import {referencedFrameBuffers} from '../src/components/viewport3d/viewport-frame-codec';
import {workerDataStore} from '../src/components/viewport3d/WorkerDataStore';

const receiver = new ViewportFrameReceiver((message, transfer) => self.postMessage(message, {transfer: transfer ?? []}),
    (stream, frame) => workerDataStore.dispatch(stream, frame),
    () => referencedFrameBuffers(workerDataStore.getLatestKeypoints(), workerDataStore.getLatestModelFrames()),
    () => workerDataStore.dispatch('frameReset', null));
workerDataStore.subscribeToModelFrames(() => receiver.scheduleRelease());
self.onmessage = event => {
    if (receiver.receive(event.data)) return;
    if (event.data.type === 'probe') self.postMessage({type: 'probe', id: event.data.id,
        models: workerDataStore.getLatestModelFrames()?.length ?? 0});
    else workerDataStore.dispatch(event.data.type, event.data.data);
};
