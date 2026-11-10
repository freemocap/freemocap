// Run tools/test-camera-settings.mjs <ignored-output.cjs> src/store/slices/cameras/camera-settings-storage.test.ts
import assert from 'node:assert/strict';
import {createDefaultCameraConfig, DEFAULT_CAMERA_FRAMERATE} from './cameras-types';
import {
    buildPersistedEntry,
    loadPersistedCameraSettings,
    migratePersistedCameraSettings,
    PersistedCameraSettingsMap,
} from './camera-settings-storage';

// New cameras request an explicit rate instead of the camera's own, possibly maximum, default.
const config = createDefaultCameraConfig('camera-A', 0, 'Global Shutter Camera');
assert.equal(DEFAULT_CAMERA_FRAMERATE, 30);
assert.equal(config.framerate, DEFAULT_CAMERA_FRAMERATE);

// Entries saved before the frame-rate control existed carry the old automatic default.
const legacy: PersistedCameraSettingsMap = {
    'camera-A': {selected: true, realtimeEnabled: true, desiredConfig: {framerate: -1, exposure: -5}},
    'camera-B': {selected: false, realtimeEnabled: true, desiredConfig: {exposure: -6}},
    'camera-C': {selected: true, realtimeEnabled: false, desiredConfig: {framerate: 60}},
};
const migrated = migratePersistedCameraSettings(legacy);
assert.equal(migrated['camera-A'].desiredConfig.framerate, 30);
assert.equal(migrated['camera-A'].desiredConfig.exposure, -5);
assert.equal(migrated['camera-A'].selected, true);
assert.equal(migrated['camera-B'].desiredConfig.framerate, 30);
assert.equal(migrated['camera-B'].selected, false);
assert.equal(migrated['camera-C'].desiredConfig.framerate, 60);
assert.equal(migrated['camera-C'].realtimeEnabled, false);
assert.ok(Object.values(migrated).every(entry => entry.settingsVersion === 2));
assert.equal(legacy['camera-A'].desiredConfig.framerate, -1, 'migration must not mutate its input');

// An automatic rate chosen with the control is saved as version 2 and survives reloads.
const autoEntry = buildPersistedEntry({...config, framerate: -1}, true, true);
assert.equal(autoEntry.settingsVersion, 2);
assert.equal(migratePersistedCameraSettings({'camera-A': autoEntry})['camera-A'].desiredConfig.framerate, -1);

// Loading saved settings applies the migration.
const stored = JSON.stringify(legacy);
Object.defineProperty(globalThis, 'localStorage', {configurable: true, value: {
    getItem: () => stored, setItem: () => {}, removeItem: () => {}, clear: () => {}, key: () => null, length: 0,
}});
assert.equal(loadPersistedCameraSettings()['camera-A'].desiredConfig.framerate, 30);

console.log('camera settings storage tests passed');
