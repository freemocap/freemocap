import assert from 'node:assert/strict';
import {test} from 'node:test';
import {migrateExportSettings} from './export-settings-migration';

test('historical browser settings retain formats, channels, overrides and automatic export choice', () => {
    const saved = {scientificExportFormats: ['npz'], scientificExportData: ['RAW_KEYPOINTS_3D'],
        scientificExportChannels: [{channel: 'RAW_KEYPOINTS_3D'}], scientificExportAfterProcessing: true,
        exportTallCsv: true, detectorType: 'rtmpose'};
    const result = migrateExportSettings(saved);
    assert.equal(result.error, null);
    assert.deepEqual(result.config, {exportFormats: ['npz'], exportChannels: ['RAW_KEYPOINTS_3D'],
        exportChannelOverrides: [{channel: 'RAW_KEYPOINTS_3D'}], exportAfterProcessing: true,
        exportTallCsv: true, detectorType: 'rtmpose'});
    assert.ok('scientificExportFormats' in saved, 'Reading settings does not rewrite their source');
    assert.deepEqual(migrateExportSettings(result.config), result);
});

test('conflicting settings produce an explicit error and preserve unrelated preferences', () => {
    const result = migrateExportSettings({scientificExportFormats: ['npy'], exportFormats: ['npz'],
        exportAfterProcessing: true, detectorType: 'rtmpose'});
    assert.match(result.error!, /conflict.*exportFormats/);
    assert.deepEqual(result.config, {detectorType: 'rtmpose'});
    assert.deepEqual(migrateExportSettings({scientificExportFormats: ['npy'], exportFormats: ['npy']}),
        {config: {exportFormats: ['npy']}, error: null});
});
