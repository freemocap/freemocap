/**
 * Helpers for deriving paths from the FreeMoCap base data folder.
 *
 * The base data folder itself is owned by the Electron main process (see
 * electron/main/base-folder.ts) and fetched via `api.fileSystem.getBaseDataFolder`.
 * The renderer only derives subpaths from it — it never hardcodes the folder name.
 */

/** The recordings subdirectory that lives inside the base data folder. */
export const RECORDINGS_SUBDIR = 'recordings';

/**
 * Join the base data folder with the recordings subdirectory, preserving the platform's
 * path separator (backslash on Windows, forward slash elsewhere).
 */
export function recordingsDirFromBaseFolder(baseFolder: string): string {
    const sep = baseFolder.includes('\\') ? '\\' : '/';
    const trimmed = baseFolder.replace(/[\\/]+$/, '');
    return `${trimmed}${sep}${RECORDINGS_SUBDIR}`;
}
