import {parquetMetadata, parquetRead, type ColumnData} from 'hyparquet';
import {compressors} from 'hyparquet-compressors';
import {z} from 'zod';
import {RecordingChannelKind, type PlaybackManifest, type PlaybackChannelData, type RecordingChannel} from './playback-data';

const SampleSchema = z.object({
    run_id: z.coerce.number().int().nonnegative(),
    sensor_group: z.string(), source: z.string(), reference_frame: z.string().nullable(),
    channel: z.string(), name: z.string(), component: z.string(), units: z.string(),
    frame_number: z.coerce.number().int().nonnegative(), timestamp_s: z.number(),
    value: z.number().nullable(),
});
const SceneKindSchema = z.enum(RecordingChannelKind);
const sampleColumns = SampleSchema.keyof().options;
const key = (run: number, group: string, source: string, reference: string | null, kind: string) =>
    JSON.stringify([run, group, source, reference, kind]);

export async function decodePlaybackParquet(file: ArrayBuffer, manifest: PlaybackManifest): Promise<Record<number, PlaybackChannelData[]>> {
    const metadata = parquetMetadata(file);
    const builders = new Map<string, {
        runId: number; channel: RecordingChannel; names: Map<string, number>;
        components: Map<string, number>; stride: number;
        frames: Map<number, {time: number; values: Float64Array; seen: Uint8Array}>;
    }>();
    for (const run of manifest.runs) {
        for (const channel of run.channels) {
            if (!SceneKindSchema.safeParse(channel.kind).success) continue;
            const channelKey = key(run.run_id, channel.sensor_group, channel.source, channel.reference_frame, channel.kind);
            if (builders.has(channelKey)) throw new Error('Duplicate playback channel declaration');
            builders.set(channelKey, {runId: run.run_id, channel,
                names: new Map(channel.names.map((name, index) => [name, index])),
                components: new Map(Object.keys(channel.components).map((name, index) => [name, index])),
                stride: channel.names.length * Object.keys(channel.components).length, frames: new Map()});
        }
    }
    let rowStart = 0;
    for (const group of metadata.row_groups) {
        const rowEnd = rowStart + Number(group.num_rows);
        const columns = new Map<string, {chunks: ColumnData[]; index: number}>();
        await parquetRead({file, metadata, compressors, columns: sampleColumns,
            rowStart, rowEnd, onChunk: chunk => {
                let column = columns.get(chunk.columnName);
                if (!column) {column = {chunks: [], index: 0}; columns.set(chunk.columnName, column);}
                column.chunks.push(chunk);
            }});
        for (const column of columns.values()) column.chunks.sort((left, right) => left.rowStart - right.rowStart);
        const read = (name: keyof z.infer<typeof SampleSchema>, row: number): unknown => {
            const column = columns.get(name);
            if (!column) throw new Error('Missing Parquet column');
            while (column.index < column.chunks.length && row >= column.chunks[column.index].rowEnd) column.index++;
            const chunk = column.chunks[column.index];
            if (!chunk || row < chunk.rowStart) throw new Error('Incomplete Parquet columns');
            return chunk.columnData[row - chunk.rowStart];
        };
        for (let row = rowStart; row < rowEnd; row++) {
            const builder = builders.get(key(Number(read('run_id', row)), String(read('sensor_group', row)),
                String(read('source', row)), read('reference_frame', row) as string | null, String(read('channel', row))));
            if (!builder) continue;
            const sample = SampleSchema.parse(Object.fromEntries(sampleColumns.map(name => [name, read(name, row)])));
            const nameIndex = builder.names.get(sample.name);
            const componentIndex = builder.components.get(sample.component);
            if (nameIndex === undefined || componentIndex === undefined ||
                builder.channel.components[sample.component] !== sample.units) throw new Error('Sample does not match its playback channel declaration');
            let frame = builder.frames.get(sample.frame_number);
            if (!frame) {
                frame = {time: sample.timestamp_s, values: new Float64Array(builder.stride).fill(NaN), seen: new Uint8Array(builder.stride)};
                builder.frames.set(sample.frame_number, frame);
            }
            const offset = nameIndex * builder.components.size + componentIndex;
            if (frame.time !== sample.timestamp_s || frame.seen[offset]) throw new Error('Duplicate or inconsistent playback sample');
            frame.values[offset] = sample.value ?? NaN;
            frame.seen[offset] = 1;
        }
        rowStart = rowEnd;
    }
    const result: Record<number, PlaybackChannelData[]> = Object.fromEntries(manifest.runs.map(run => [run.run_id, []]));
    for (const builder of builders.values()) {
        const frames = [...builder.frames].sort(([left], [right]) => left - right);
        if (!frames.length) continue;
        const values = new Float64Array(frames.length * builder.stride);
        const timestamps: number[] = [];
        const frameNumbers: number[] = [];
        for (const [index, [number, frame]] of frames.entries()) {
            if (frame.seen.includes(0)) throw new Error('Incomplete playback sample grid');
            if (index && frame.time <= timestamps[index - 1]) throw new Error('Playback timestamps must increase');
            timestamps.push(frame.time); frameNumbers.push(number);
            values.set(frame.values, index * builder.stride);
        }
        result[builder.runId].push({channel: builder.channel, frame_numbers: frameNumbers, timestamps_s: timestamps, values});
    }
    return result;
}
