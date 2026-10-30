import {parquetMetadata, parquetRead, type ColumnData} from 'hyparquet';
import {compressors} from 'hyparquet-compressors';
import {RecordingChannelKind, type PlaybackManifest, type PlaybackChannelData, type RecordingChannel} from './playback-data';

const IDENTITY_COLUMNS = ['run_id', 'sensor_group', 'source', 'reference_frame', 'channel', 'frame_number'];
const VALUE_COLUMNS = ['name', 'component', 'units', 'timestamp_s', 'value'];
const SCENE_KINDS = new Set<string>(Object.values(RecordingChannelKind));
type ParquetMetadata = ReturnType<typeof parquetMetadata>;
type ChannelLookup = Map<number, Map<string, Map<string, Map<string | null, Map<string, number>>>>>;
interface ColumnSpan {values: ArrayLike<unknown>; offset: number}
interface ChannelAssembly {
    runId: number;
    channel: RecordingChannel;
    names: Map<string, number>;
    components: Map<string, number>;
    componentUnits: string[];
    stride: number;
    frameSlots: Map<number, number>;
    previousFrame: number;
    previousSlot: number;
    frameOrder: Uint32Array;
    frameNumbers: number[];
    timestamps: number[];
    values: Float64Array<ArrayBuffer>;
    seen: Uint8Array;
}

function unsignedInteger(value: unknown, label: string): number {
    const number = typeof value === 'bigint' ? Number(value) : value;
    if (typeof number !== 'number' || !Number.isSafeInteger(number) || number < 0) {
        throw new Error(`Invalid playback ${label}: expected a nonnegative safe integer`);
    }
    return number;
}

function validateColumns(metadata: ParquetMetadata): void {
    for (const name of [...IDENTITY_COLUMNS, ...VALUE_COLUMNS]) {
        const fields = metadata.schema.filter(field => field.name === name);
        const field = fields[0];
        if (fields.length !== 1 || !field || field.num_children) throw new Error(`Missing or invalid Parquet column: ${name}`);
        const allowed = name === 'run_id' || name === 'frame_number' ? ['INT32', 'INT64']
            : name === 'timestamp_s' || name === 'value' ? ['FLOAT', 'DOUBLE'] : ['BYTE_ARRAY'];
        if (!field.type || !allowed.includes(field.type)) throw new Error(`Invalid Parquet column type: ${name}`);
    }
}

/** Visit aligned column spans without materializing rows or copying page slices. */
async function visitColumnSpans(file: ArrayBuffer, metadata: ParquetMetadata, names: string[],
    visit: (columns: ColumnSpan[], rowStart: number, count: number) => void): Promise<void> {
    let groupStart = 0;
    for (const group of metadata.row_groups) {
        const groupEnd = groupStart + unsignedInteger(group.num_rows, 'row count');
        const chunks = new Map(names.map(name => [name, [] as ColumnData[]]));
        await parquetRead({file, metadata, compressors, columns: names, rowStart: groupStart, rowEnd: groupEnd,
            onChunk: chunk => {
                const column = chunks.get(chunk.columnName);
                if (!column) throw new Error('Unexpected Parquet column');
                column.push(chunk);
            }});
        const columns = names.map(name => chunks.get(name)!);
        for (const column of columns) {
            column.sort((left, right) => left.rowStart - right.rowStart);
            let nextRow = groupStart;
            for (const chunk of column) {
                if (chunk.rowStart !== nextRow || chunk.rowEnd <= chunk.rowStart || chunk.rowEnd > groupEnd ||
                    chunk.columnData.length !== chunk.rowEnd - chunk.rowStart) throw new Error('Incomplete or overlapping Parquet columns');
                nextRow = chunk.rowEnd;
            }
            if (nextRow !== groupEnd) throw new Error('Incomplete Parquet columns');
        }
        const positions = new Uint32Array(columns.length);
        let rowStart = groupStart;
        while (rowStart < groupEnd) {
            let rowEnd = groupEnd;
            const spans = columns.map((column, index) => {
                while (rowStart >= column[positions[index]].rowEnd) positions[index]++;
                const chunk = column[positions[index]];
                rowEnd = Math.min(rowEnd, chunk.rowEnd);
                return {values: chunk.columnData, offset: rowStart - chunk.rowStart};
            });
            visit(spans, rowStart, rowEnd - rowStart);
            rowStart = rowEnd;
        }
        groupStart = groupEnd;
    }
    if (groupStart !== unsignedInteger(metadata.num_rows, 'row count')) throw new Error('Inconsistent Parquet row count');
}

export async function decodePlaybackParquet(file: ArrayBuffer, manifest: PlaybackManifest): Promise<Record<number, PlaybackChannelData[]>> {
    const metadata = parquetMetadata(file);
    validateColumns(metadata);
    const rowCount = unsignedInteger(metadata.num_rows, 'row count');
    const channelRows = new Int32Array(rowCount).fill(-1);
    const frameRows = new Uint32Array(rowCount);
    const lookup: ChannelLookup = new Map();
    const assemblies: ChannelAssembly[] = [];
    const result: Record<number, PlaybackChannelData[]> = {};
    for (const run of manifest.runs) {
        const runId = unsignedInteger(run.run_id, 'run ID');
        if (Object.hasOwn(result, runId)) throw new Error('Duplicate playback run declaration');
        result[runId] = [];
        const groups = new Map<string, Map<string, Map<string | null, Map<string, number>>>>();
        lookup.set(runId, groups);
        for (const channel of run.channels) {
            if (!SCENE_KINDS.has(channel.kind)) continue;
            // These maps describe authored axes; numerical values live only in typed arrays.
            const names = new Map(channel.names.map((name, index) => [name, index]));
            const components = new Map(Object.keys(channel.components).map((name, index) => [name, index]));
            if (!names.size || names.size !== channel.names.length || !components.size) throw new Error('Invalid playback channel layout');
            let sources = groups.get(channel.sensor_group);
            if (!sources) {sources = new Map(); groups.set(channel.sensor_group, sources);}
            let references = sources.get(channel.source);
            if (!references) {references = new Map(); sources.set(channel.source, references);}
            let kinds = references.get(channel.reference_frame);
            if (!kinds) {kinds = new Map(); references.set(channel.reference_frame, kinds);}
            if (kinds.has(channel.kind)) throw new Error('Duplicate playback channel declaration');
            kinds.set(channel.kind, assemblies.length);
            assemblies.push({runId, channel, names, components, componentUnits: Object.values(channel.components),
                stride: names.size * components.size, frameSlots: new Map(), previousFrame: -1, previousSlot: -1,
                frameOrder: new Uint32Array(), frameNumbers: [], timestamps: [], values: new Float64Array(), seen: new Uint8Array()});
        }
    }

    // Each column is decoded once. First resolve axes and identity, then write
    // values into exactly sized recording tensors using the prepared row indices.
    await visitColumnSpans(file, metadata, IDENTITY_COLUMNS, ([runs, groups, sources, references, kinds, frames], rowStart, count) => {
        let previousRun: unknown, previousGroup: unknown, previousSource: unknown, previousReference: unknown, previousKind: unknown;
        let channelIndex = -1;
        for (let row = 0; row < count; row++) {
            const run = runs.values[runs.offset + row], group = groups.values[groups.offset + row];
            const source = sources.values[sources.offset + row], reference = references.values[references.offset + row];
            const kind = kinds.values[kinds.offset + row];
            if (row === 0 || run !== previousRun || group !== previousGroup || source !== previousSource || reference !== previousReference || kind !== previousKind) {
                const runId = unsignedInteger(run, 'run ID');
                if (typeof group !== 'string' || typeof source !== 'string' || typeof kind !== 'string' ||
                    (reference !== null && typeof reference !== 'string')) throw new Error('Invalid playback source identity');
                channelIndex = lookup.get(runId)?.get(group)?.get(source)?.get(reference)?.get(kind) ?? -1;
                previousRun = run; previousGroup = group; previousSource = source; previousReference = reference; previousKind = kind;
            }
            if (channelIndex < 0) continue;
            const assembly = assemblies[channelIndex];
            const frame = unsignedInteger(frames.values[frames.offset + row], 'frame number');
            if (frame !== assembly.previousFrame) {
                let slot = assembly.frameSlots.get(frame);
                if (slot === undefined) {slot = assembly.frameSlots.size; assembly.frameSlots.set(frame, slot);}
                assembly.previousFrame = frame; assembly.previousSlot = slot;
            }
            channelRows[rowStart + row] = channelIndex;
            frameRows[rowStart + row] = assembly.previousSlot;
        }
    });
    for (const assembly of assemblies) {
        assembly.frameNumbers = [...assembly.frameSlots.keys()].sort((left, right) => left - right);
        assembly.frameOrder = new Uint32Array(assembly.frameNumbers.length);
        assembly.frameNumbers.forEach((frame, index) => {assembly.frameOrder[assembly.frameSlots.get(frame)!] = index;});
        assembly.frameSlots.clear();
        assembly.timestamps = new Array<number>(assembly.frameNumbers.length).fill(NaN);
        assembly.values = new Float64Array(assembly.frameNumbers.length * assembly.stride);
        assembly.seen = new Uint8Array(assembly.values.length);
    }
    await visitColumnSpans(file, metadata, VALUE_COLUMNS, ([names, components, units, times, values], rowStart, count) => {
        for (let row = 0; row < count; row++) {
            const channelIndex = channelRows[rowStart + row];
            if (channelIndex < 0) continue;
            const assembly = assemblies[channelIndex];
            const name = names.values[names.offset + row], component = components.values[components.offset + row];
            const nameIndex = assembly.names.get(name as string), componentIndex = assembly.components.get(component as string);
            if (nameIndex === undefined || componentIndex === undefined || units.values[units.offset + row] !== assembly.componentUnits[componentIndex]) {
                throw new Error('Sample does not match its playback channel declaration');
            }
            const time = times.values[times.offset + row], value = values.values[values.offset + row];
            if (typeof time !== 'number' || !Number.isFinite(time) ||
                (value !== null && (typeof value !== 'number' || !Number.isFinite(value)))) throw new Error('Invalid playback numerical value or timestamp');
            const frameIndex = assembly.frameOrder[frameRows[rowStart + row]];
            const offset = frameIndex * assembly.stride + nameIndex * assembly.components.size + componentIndex;
            const previousTime = assembly.timestamps[frameIndex];
            if ((!Number.isNaN(previousTime) && previousTime !== time) || assembly.seen[offset]) throw new Error('Duplicate or inconsistent playback sample');
            assembly.timestamps[frameIndex] = time;
            assembly.values[offset] = value ?? NaN;
            assembly.seen[offset] = 1;
        }
    });
    for (const assembly of assemblies) {
        if (!assembly.frameNumbers.length) continue;
        if (assembly.seen.includes(0)) throw new Error('Incomplete playback sample grid');
        for (let frame = 1; frame < assembly.timestamps.length; frame++) {
            if (assembly.timestamps[frame] <= assembly.timestamps[frame - 1]) throw new Error('Playback timestamps must increase');
        }
        result[assembly.runId].push({channel: assembly.channel, frame_numbers: assembly.frameNumbers,
            timestamps_s: assembly.timestamps, values: assembly.values});
    }
    return result;
}
