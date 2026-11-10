import assert from 'node:assert/strict';
import {test} from 'node:test';
import {
    GROWABLE_MIN_PX,
    planSidebarSections,
    SECTION_MIN_PX,
    type SectionPlan,
} from './sidebar-section-layout';

const STREAMING = ['cameras', 'calibration', 'recording_path', 'recording_control'] as const;
const GROWABLE = new Set(['cameras']);
const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);
const px = (plan: SectionPlan, index: number, availablePx: number) => plan.sizes[index] * availablePx / 100;

function assertValid(plan: SectionPlan) {
    assert.ok(Math.abs(sum(plan.sizes) - 100) < 1e-6, `sizes sum to ${sum(plan.sizes)}`);
    plan.sizes.forEach((size, index) => {
        assert.ok(size >= 0, `size ${index} is ${size}`);
        assert.ok(plan.minSizes[index] >= 0, `min ${index} is ${plan.minSizes[index]}`);
        assert.ok(plan.minSizes[index] <= size + 1e-9, `min ${plan.minSizes[index]} exceeds size ${size}`);
    });
}

test('content that fits keeps every section at its content and gives cameras the rest', () => {
    const availablePx = 630;
    const plan = planSidebarSections({sections: STREAMING, growable: GROWABLE, availablePx,
        contentPx: {calibration: 150, recording_path: 76, recording_control: 95}});
    assertValid(plan);
    assert.ok(Math.abs(px(plan, 1, availablePx) - 150) < 1e-6);
    assert.ok(Math.abs(px(plan, 2, availablePx) - 76) < 1e-6);
    assert.ok(Math.abs(px(plan, 3, availablePx) - 95) < 1e-6);
    assert.ok(Math.abs(px(plan, 0, availablePx) - (630 - 150 - 76 - 95)) < 1e-6);
});

test('expanded sections can never take the camera floor', () => {
    // The reported failure: at 1280x720 the old policy left cameras 47-93 px (0 of 5 rows).
    for (const availablePx of [260, 400, 630, 900, 1400]) {
        for (const calibration of [0, 150, 263, 600, 2000]) {
            for (const recordingControl of [40, 95, 220, 900]) {
                const plan = planSidebarSections({sections: STREAMING, growable: GROWABLE, availablePx,
                    contentPx: {calibration, recording_path: 76, recording_control: recordingControl}});
                assertValid(plan);
                const floorPx = Math.min(GROWABLE_MIN_PX, availablePx * 0.75);
                assert.ok(px(plan, 0, availablePx) >= floorPx - 1e-6,
                    `cameras got ${px(plan, 0, availablePx)} px of ${availablePx}`);
                assert.ok(plan.minSizes[0] * availablePx / 100 >= floorPx - 1e-6, 'camera min size protects the floor');
            }
        }
    }
});

test('the tallest section is trimmed first and scrolls; small sections keep their content', () => {
    const availablePx = 630;
    const plan = planSidebarSections({sections: STREAMING, growable: GROWABLE, availablePx,
        contentPx: {calibration: 600, recording_path: 76, recording_control: 95}});
    assertValid(plan);
    assert.ok(Math.abs(px(plan, 0, availablePx) - GROWABLE_MIN_PX) < 1e-6, 'cameras sit exactly at the floor');
    assert.ok(Math.abs(px(plan, 2, availablePx) - 76) < 1e-6, 'recording path keeps its content');
    assert.ok(Math.abs(px(plan, 3, availablePx) - 95) < 1e-6, 'record controls keep their content');
    assert.ok(px(plan, 1, availablePx) < 600, 'calibration is capped and scrolls');
});

test('very short sidebars keep a capped camera share and a first row for every section', () => {
    const availablePx = 240;
    const plan = planSidebarSections({sections: STREAMING, growable: GROWABLE, availablePx,
        contentPx: {calibration: 400, recording_path: 76, recording_control: 220}});
    assertValid(plan);
    assert.ok(Math.abs(px(plan, 0, availablePx) - availablePx * 0.75) < 1e-6);
    for (const index of [1, 2, 3]) assert.ok(px(plan, index, availablePx) > 0);
    const tall = planSidebarSections({sections: STREAMING, growable: GROWABLE, availablePx: 800,
        contentPx: {calibration: 2000, recording_path: 2000, recording_control: 2000}});
    assertValid(tall);
    for (const index of [1, 2, 3]) assert.ok(px(tall, index, 800) >= SECTION_MIN_PX - 1e-6);
});

test('before measurement the plan is still a valid layout that favours cameras', () => {
    const plan = planSidebarSections({sections: STREAMING, growable: GROWABLE, availablePx: 0, contentPx: {}});
    assertValid(plan);
    assert.ok(plan.sizes[0] > 50);
});

test('playback keeps the recording browser floor; sections without a growable fill the space', () => {
    const playback = planSidebarSections({sections: ['recordings', 'calibration', 'process_mocap'],
        growable: new Set(['recordings']), availablePx: 500, contentPx: {calibration: 700, process_mocap: 50}});
    assertValid(playback);
    assert.ok(px(playback, 0, 500) >= GROWABLE_MIN_PX - 1e-6);
    const fixedOnly = planSidebarSections({sections: ['calibration', 'process_mocap'], growable: new Set(),
        availablePx: 500, contentPx: {calibration: 120, process_mocap: 50}});
    assertValid(fixedOnly);
    assert.ok(px(fixedOnly, 0, 500) >= 120 - 1e-6 && px(fixedOnly, 1, 500) >= 50 - 1e-6);
});
