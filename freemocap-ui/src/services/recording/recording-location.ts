/** A folder name is unique only within its recording parent directory. */
export interface RecordingLocation {
    recordingId: string;
    recordingParentDirectory?: string | null;
}

export function recordingLocationKey(recordingId: string, parent?: string | null): string {
    return JSON.stringify([parent || null, recordingId]);
}

/** Split a server filesystem path without assuming the browser's operating system. */
export function recordingLocationFromPath(path: string): RecordingLocation {
    const trimmed = path.replace(/[\\/]+$/, '');
    const separator = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
    if (separator < 0 || separator === trimmed.length - 1) throw new Error('Expected a full recording path');
    const recordingId = trimmed.slice(separator + 1);
    if (!recordingId || recordingId === '.' || recordingId === '..') throw new Error('Invalid recording folder');
    const parent = separator === 0 ? trimmed.slice(0, 1)
        : separator === 2 && trimmed[1] === ':' ? trimmed.slice(0, 3) : trimmed.slice(0, separator);
    return {recordingId, recordingParentDirectory: parent};
}

export function recordingQuery(parent?: string | null, values: Record<string, string> = {}): string {
    const parameters = new URLSearchParams(values);
    if (parent) parameters.set('recording_parent_directory', parent);
    const query = parameters.toString();
    return query ? `?${query}` : '';
}
