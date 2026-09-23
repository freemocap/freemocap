import {decodePlaybackParquet} from './playback-parquet';
import {PlaybackLoadRequestSchema, type PlaybackLoadResult} from './playback-parquet-messages';

const workerScope = self as unknown as Worker;

self.addEventListener('message', (event: MessageEvent<unknown>) => {
    void load(event.data);
});

async function load(input: unknown): Promise<void> {
    try {
        const {url, manifest} = PlaybackLoadRequestSchema.parse(input);
        const response = await fetch(url, {cache: 'no-store'});
        if (!response.ok) throw new Error(`Unable to load recording data: ${await response.text()}`);
        if (response.headers.get('ETag') !== `"${manifest.revision}"`) {
            throw new Error('Recording changed; reload the playback manifest');
        }
        const runs = await decodePlaybackParquet(await response.arrayBuffer(), manifest);
        const transfers: ArrayBuffer[] = [];
        for (const channels of Object.values(runs)) {
            for (const channel of channels) {
                if (channel.values instanceof Float64Array) transfers.push(channel.values.buffer as ArrayBuffer);
            }
        }
        const result: PlaybackLoadResult = {success: true, runs};
        workerScope.postMessage(result, transfers);
    } catch (error) {
        const result: PlaybackLoadResult = {
            success: false, message: error instanceof Error ? error.message : String(error),
        };
        workerScope.postMessage(result);
    }
}
