// One-off test (no unit-test framework in this project — run via esbuild+node).
// Reproduces the duplicate-camera_index collision seen in the backend log:
//   ValueError: Camera indexes must be unique ... {'be07': 0, 'fa5a': 1, '583d': 1}
//
// Run:
//   node_modules/.bin/esbuild src/store/slices/cameras/cameras-reconcile.test.ts \
//     --bundle --platform=node --format=esm --outfile=.tmp-reconcile-test.mjs \
//   && node .tmp-reconcile-test.mjs

import {Camera, createDefaultCameraConfig, reconcileDetectedCameras} from './cameras-types';

// Tiny framework-free assert so this file type-checks under the app's
// (browser) tsconfig and still runs under node via esbuild.
function assertEqual<T>(actual: T, expected: T, message: string): void {
    if (actual !== expected) {
        throw new Error(`${message} (expected ${String(expected)}, got ${String(actual)})`);
    }
}

function makeCamera(id: string, index: number, name: string, tune?: {exposure?: number}): Camera {
    const desiredConfig = {
        ...createDefaultCameraConfig(id, index, name),
        ...(tune?.exposure !== undefined ? {exposure: tune.exposure} : {}),
    };
    return {
        id,
        index,
        name,
        actualConfig: createDefaultCameraConfig(id, index, name),
        desiredConfig,
        hasConfigMismatch: false,
        connectionStatus: 'available',
        selected: true,
        realtimeEnabled: true,
        deviceInfo: {},
        metrics: undefined,
    };
}

// State BEFORE the new camera was plugged in: fa5a is at OS index 1, and the
// user tuned its exposure to -5 (so we can prove settings survive the merge).
const previousCameras: Camera[] = [
    makeCamera('be07', 0, 'USB Camera'),
    makeCamera('fa5a', 1, 'USB Camera', {exposure: -5}),
];

// Fresh detection AFTER plugging in 583d: Windows renumbered the ports, so the
// same physical camera fa5a (stable id) now enumerates at index 2, and the new
// camera 583d took over index 1. Every detected camera carries its FRESH index.
const detectedCameras: Camera[] = [
    makeCamera('be07', 0, 'USB Camera'),
    makeCamera('fa5a', 2, 'USB Camera'),
    makeCamera('583d', 1, 'USB Camera'),
];

const merged = reconcileDetectedCameras(previousCameras, detectedCameras);

// What actually gets sent to the backend is desiredConfig (see selectSelectedCameraConfigs).
const indexesById = Object.fromEntries(
    merged.map(c => [c.id, c.desiredConfig.camera_index]),
);
console.log('resulting desiredConfig.camera_index by id:', JSON.stringify(indexesById));

// 1) The volatile index must be refreshed from detection, not carried over stale.
const fa5a = merged.find(c => c.id === 'fa5a')!;
assertEqual(
    fa5a.desiredConfig.camera_index,
    2,
    'fa5a.desiredConfig.camera_index should refresh to the detected index (stale index carried over)',
);

// 2) The whole point: no two cameras may claim the same index (backend rejects it).
const indexes = merged.map(c => c.desiredConfig.camera_index);
assertEqual(
    new Set(indexes).size,
    indexes.length,
    `camera_index values must be unique across configs, got ${JSON.stringify(indexesById)}`,
);

// 3) The merge must NOT clobber user-tuned settings while refreshing identity.
assertEqual(
    fa5a.desiredConfig.exposure,
    -5,
    "fa5a's tuned exposure (-5) must survive the merge",
);

console.log('PASS: reconcileDetectedCameras refreshes volatile index and keeps tuned settings');
