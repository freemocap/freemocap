import {fileURLToPath} from 'node:url';

export const clientRoot = fileURLToPath(new URL('../../packages/freemocap-client/', import.meta.url));

// Match only public exports. Serve source so linked-package build artifacts and
// Vite's dependency cache cannot hide edits from the development module graph.
export const clientAliases = Object.entries({
    '': 'index.ts',
    '/http': 'http.ts',
    '/images': 'images/index.ts',
    '/recording': 'recording/index.ts',
}).map(([suffix, entry]) => ({
    find: new RegExp(`^@freemocap/client${suffix}$`),
    replacement: fileURLToPath(new URL(`../../packages/freemocap-client/src/${entry}`, import.meta.url)),
}));
