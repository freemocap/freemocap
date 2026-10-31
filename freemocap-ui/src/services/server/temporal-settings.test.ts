// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {requestTemporalSettings} from './temporal-settings';
import {sameTemporalConfig, type TemporalConfig} from '@/types/temporal-config';

const config: TemporalConfig = {
    image_smoothing: {enabled: false, min_cutoff: 1, beta: .0001, d_cutoff: 1},
    spatial_smoothing: {enabled: true, min_cutoff: 1, beta: .01, d_cutoff: 1},
    velocity_gate_enabled: true, max_velocity_mm_per_s: 50000, reacquisition_timeout_s: .3,
    gap_duration_s: .3, prediction_duration_s: .1, velocity_half_life_s: .08,
    segment_retention_s: .3, max_reprojection_error_px: 60, segment_scale_window_frames: 30,
};

test('filter updates preserve units and distinguish requested settings from worker-confirmed settings', async context => {
    const requested = {...config, gap_duration_s: .5};
    let sent: RequestInit | undefined;
    context.mock.method(globalThis, 'fetch', async (url: string, init?: RequestInit) => {
        assert.equal(url, '/freemocap/realtime/filter-config');
        sent = init;
        return Response.json({defaults: config, requested, applied: config});
    });
    const result = await requestTemporalSettings('/freemocap/realtime/filter-config', requested);
    assert.equal(sent?.method, 'PUT');
    assert.deepEqual(JSON.parse(sent?.body as string), requested);
    assert.equal(result.requested?.gap_duration_s, .5);
    assert.equal(result.applied?.gap_duration_s, .3);
    assert.equal(sameTemporalConfig(result.requested, result.applied), false);
    assert.equal(sameTemporalConfig({...config, spatial_smoothing: {...config.spatial_smoothing}}, config), true);
});

test('defaults can be read without creating a pipeline and server validation errors reach the caller', async context => {
    context.mock.method(globalThis, 'fetch', async (_url: string, init?: RequestInit) => {
        assert.equal(init, undefined);
        return Response.json({defaults: config, requested: null, applied: null});
    });
    assert.deepEqual((await requestTemporalSettings('/settings')).defaults, config);
    context.mock.method(globalThis, 'fetch', async () => Response.json({detail: 'No running realtime pipeline'}, {status: 409}));
    await assert.rejects(requestTemporalSettings('/settings', config), /No running realtime pipeline/);
});
