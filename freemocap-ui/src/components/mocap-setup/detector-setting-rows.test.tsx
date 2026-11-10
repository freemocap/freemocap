// Run: node src/components/realtime-processing/run-realtime-processing-tests.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Children, isValidElement, type ReactElement, type ReactNode} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
// The store import follows the application entry order: the detector rows take their model list from the mocap slice.
import '@/store';
import type {TriangulationConfig} from '@/store/slices/mocap';
import type {RealtimeDetectorType} from '@/store/slices/realtime/realtime-types';
import {EXECUTION_PROVIDERS} from '@/types/execution-provider';
import {DETECTOR_OPTIONS, REALTIME_DETECTOR_OPTIONS} from './detector-options';
import {DetectorSettingRows, type DetectorSettingsValue} from './detector-setting-rows';
import {OutlierRejectionRows} from './outlier-rejection-rows';
import SkeletonAnchorSetting from './skeleton-anchor-setting';

type DetectorRowsProps = Parameters<typeof DetectorSettingRows>[0];
type Handler = (value: string | number | boolean) => void;
interface RowProps {label?: ReactNode; control?: ReactElement<{onChange?: Handler; onToggle?: Handler}>; children?: ReactNode}

const DETECTORS: RealtimeDetectorType[] = ['rtmpose', 'mediapipe', 'rtmw_mediapipe_hands', 'dlc', 'rtmw_onnx_hands'];
/** The realtime pipeline's detector defaults. */
const VALUE: DetectorSettingsValue = {
    detector: 'rtmpose', model: 'rtmw-x-l_256x192', provider: null, confidence: 0.0025,
    poseModelSize: 'lite', detectionConfidence: 0.5, presenceConfidence: 0.5, trackingConfidence: 0.5,
};
const CONFIG: TriangulationConfig = {
    use_outlier_rejection: true, minimum_cameras_for_triangulation: 2, maximum_cameras_to_drop: 1, target_reprojection_error: 0.02,
};
const OUTLIER_LIMITS = ['Minimum cameras for triangulation', 'Maximum cameras to drop', 'Target reprojection error'];

/** The detector rows' props as the realtime controls pass them, for one detector. */
const detectorProps = (detector: RealtimeDetectorType, rows: 'all' | 'key', more: Partial<DetectorRowsProps> = {}): DetectorRowsProps => ({
    value: {...VALUE, detector}, onChange: () => {}, detectors: REALTIME_DETECTOR_OPTIONS, providerOptions: EXECUTION_PROVIDERS,
    dlcControl: <button>Configure DLC</button>, context: 'realtime', rows, ...more,
});
const detectorRows = (detector: RealtimeDetectorType, rows: 'all' | 'key', more?: Partial<DetectorRowsProps>): string =>
    renderToStaticMarkup(<DetectorSettingRows {...detectorProps(detector, rows, more)}/>);
const outlierRows = (config: TriangulationConfig, inactive?: boolean): string =>
    renderToStaticMarkup(<OutlierRejectionRows config={config} onChange={() => {}} inactive={inactive}/>);

/** The opening tag of a setting row: its class list starts with the row's own class. */
const ROW = /<div class="setting-row[ "][^>]*>/;
/** Each setting row's markup, in order. A row runs from its opening tag to the next row's. */
const rowsOf = (html: string): string[] => html.split(new RegExp(`(?=${ROW.source})`)).filter(part => part.search(ROW) === 0);
/** A row's visible label. */
const labelOf = (row: string): string => row.match(/<span class="setting-row-label">([^<]*)</)?.[1] ?? '';
const labels = (html: string): string[] => rowsOf(html).map(labelOf);
const rowLabelled = (html: string, label: string): string => rowsOf(html).find(row => labelOf(row) === label) ?? '';
/** The labels of the dimmed rows. */
const dimmed = (html: string): string[] => rowsOf(html).filter(row => / setting-row-inactive[ "]/.test(row.match(ROW)?.[0] ?? '')).map(labelOf);
/** The values a row's select offers. */
const optionsOf = (row: string): string[] => [...row.matchAll(/<option value="([^"]*)"/g)].map(match => match[1]);

/**
 * The change handler of the control in the row with this label. The unit runner has no DOM to act in, so this
 * reads the handler from the elements the rows return, and the test calls it as the control would.
 */
function handlerOf(rows: ReactNode, label: string): Handler {
    const search = (node: ReactNode): Handler | undefined => {
        for (const child of Children.toArray(node)) {
            if (!isValidElement<RowProps>(child)) continue;
            const control = child.props.label === label ? child.props.control : undefined;
            const found = control ? control.props.onChange ?? control.props.onToggle : search(child.props.children);
            if (found) return found;
        }
        return undefined;
    };
    const handler = search(rows);
    assert.ok(handler, `no control with a change handler in a row labelled "${label}"`);
    return handler;
}

test('key rows are two rows for every detector', () => {
    const modelRow: Record<RealtimeDetectorType, string> = {
        rtmpose: 'Model', mediapipe: 'Pose model size', rtmw_mediapipe_hands: 'Model', dlc: 'DLC model', rtmw_onnx_hands: 'Model',
    };
    for (const detector of DETECTORS) {
        const html = detectorRows(detector, 'key');
        assert.equal(html.match(/class="setting-row[ "]/g)?.length, 2, `${detector}: ${html}`);
        assert.deepEqual(labels(html), ['Skeleton detector', modelRow[detector]], detector);
    }
    assert.deepEqual(optionsOf(rowLabelled(detectorRows('rtmpose', 'key'), 'Skeleton detector')), DETECTORS);
    assert.deepEqual(optionsOf(rowLabelled(detectorRows('rtmpose', 'key'), 'Model')), ['rtmw-x-l_256x192', 'rtmw-x-l_384x288', 'rtmw-l-m_256x192']);
    assert.deepEqual(optionsOf(rowLabelled(detectorRows('mediapipe', 'key'), 'Pose model size')), ['heavy', 'full', 'lite']);
});

test('all rows follow the detector', () => {
    const mediapipeConfidences = ['Detection confidence', 'Presence confidence', 'Tracking confidence'];
    const expected: Record<RealtimeDetectorType, string[]> = {
        rtmpose: ['Skeleton detector', 'Execution provider', 'Model', 'Confidence threshold'],
        mediapipe: ['Skeleton detector', 'Pose model size', ...mediapipeConfidences],
        rtmw_mediapipe_hands: ['Skeleton detector', 'Execution provider', 'Model', 'Confidence threshold', ...mediapipeConfidences],
        dlc: ['Skeleton detector', 'DLC model'],
        // The ONNX hand detector takes no tracking confidence.
        rtmw_onnx_hands: ['Skeleton detector', 'Execution provider', 'Model', 'Confidence threshold', 'Detection confidence', 'Presence confidence'],
    };
    for (const detector of DETECTORS) assert.deepEqual(labels(detectorRows(detector, 'all')), expected[detector], detector);
});

test('onnx hands offers only CUDA and CPU', () => {
    const providers = (detector: RealtimeDetectorType): string[] => optionsOf(rowLabelled(detectorRows(detector, 'all'), 'Execution provider'));
    assert.deepEqual(providers('rtmw_onnx_hands'), ['cuda', 'cpu']);
    // The other RTMW detectors offer every provider the caller passes; Auto stands for no provider.
    assert.deepEqual(providers('rtmpose'), ['auto', 'cuda', 'coreml', 'directml', 'cpu']);
    assert.deepEqual(providers('rtmw_mediapipe_hands'), ['auto', 'cuda', 'coreml', 'directml', 'cpu']);

    // Selecting the detector moves the provider onto CUDA, which it offers.
    const changes: Partial<DetectorSettingsValue>[] = [];
    const select = handlerOf(DetectorSettingRows(detectorProps('rtmpose', 'key', {onChange: change => changes.push(change)})), 'Skeleton detector');
    select('rtmw_mediapipe_hands');
    select('rtmw_onnx_hands');
    assert.deepEqual(changes, [{detector: 'rtmw_mediapipe_hands'}, {detector: 'rtmw_onnx_hands', provider: 'cuda'}]);
});

test('the DLC row holds the given control', () => {
    for (const rows of ['key', 'all'] as const) {
        const html = detectorRows('dlc', rows);
        assert.ok(rowLabelled(html, 'DLC model').includes('<div class="setting-row-control"><button>Configure DLC</button></div>'), html);
        assert.equal(html.split('Configure DLC').length - 1, 1, html);
    }
    for (const detector of DETECTORS.filter(other => other !== 'dlc')) {
        assert.ok(!detectorRows(detector, 'all').includes('Configure DLC'), detector);
    }
});

test('outlier rows dim with their switch', () => {
    const on = outlierRows(CONFIG);
    assert.deepEqual(labels(on), ['Use outlier rejection', ...OUTLIER_LIMITS]);
    assert.deepEqual(dimmed(on), []);
    const off = outlierRows({...CONFIG, use_outlier_rejection: false});
    assert.deepEqual(labels(off), ['Use outlier rejection', ...OUTLIER_LIMITS]);
    assert.deepEqual(dimmed(off), OUTLIER_LIMITS);
    assert.ok(!rowLabelled(off, 'Use outlier rejection').includes('disabled'), off);

    // A stage that is off dims all four rows and locks the switch, whatever the switch says.
    for (const use_outlier_rejection of [true, false]) {
        const inactive = outlierRows({...CONFIG, use_outlier_rejection}, true);
        assert.deepEqual(dimmed(inactive), ['Use outlier rejection', ...OUTLIER_LIMITS]);
        assert.match(rowLabelled(inactive, 'Use outlier rejection'), /<button type="button" role="switch"[^>]* disabled=""/);
    }
});

test('each control reports its own field', () => {
    const changes: Partial<DetectorSettingsValue>[] = [];
    const all = (detector: RealtimeDetectorType): ReactNode => DetectorSettingRows(detectorProps(detector, 'all', {onChange: change => changes.push(change)}));
    const hybrid = all('rtmw_mediapipe_hands');
    handlerOf(hybrid, 'Execution provider')('cpu');
    handlerOf(hybrid, 'Execution provider')('auto');
    handlerOf(hybrid, 'Model')('rtmw-l-m_256x192');
    handlerOf(hybrid, 'Confidence threshold')(0.3);
    handlerOf(hybrid, 'Detection confidence')(0.6);
    handlerOf(hybrid, 'Presence confidence')(0.7);
    handlerOf(hybrid, 'Tracking confidence')(0.8);
    handlerOf(all('mediapipe'), 'Pose model size')('full');
    assert.deepEqual(changes, [{provider: 'cpu'}, {provider: null}, {model: 'rtmw-l-m_256x192'}, {confidence: 0.3},
        {detectionConfidence: 0.6}, {presenceConfidence: 0.7}, {trackingConfidence: 0.8}, {poseModelSize: 'full'}]);

    // The outlier rows report the whole configuration with the one field changed.
    const configs: TriangulationConfig[] = [];
    const outlier = OutlierRejectionRows({config: CONFIG, onChange: config => configs.push(config)});
    handlerOf(outlier, 'Use outlier rejection')(false);
    handlerOf(outlier, 'Minimum cameras for triangulation')(3);
    handlerOf(outlier, 'Maximum cameras to drop')(2);
    handlerOf(outlier, 'Target reprojection error')(0.05);
    assert.deepEqual(configs, [{...CONFIG, use_outlier_rejection: false}, {...CONFIG, minimum_cameras_for_triangulation: 3},
        {...CONFIG, maximum_cameras_to_drop: 2}, {...CONFIG, target_reprojection_error: 0.05}]);
});

test('posthoc keeps its promoted detector row and its confidence step', () => {
    const posthoc = detectorRows('rtmpose', 'all', {context: 'posthoc', detectors: DETECTOR_OPTIONS});
    const realtime = detectorRows('rtmpose', 'all');
    assert.equal(posthoc.match(ROW)?.[0], '<div class="setting-row setting-row-promoted">', posthoc);
    assert.equal(realtime.match(ROW)?.[0], '<div class="setting-row">', realtime);
    assert.equal(posthoc.split('setting-row-promoted').length - 1, 1, posthoc);
    assert.ok(rowLabelled(posthoc, 'Confidence threshold').includes(' step="0.001" '), posthoc);
    assert.ok(rowLabelled(realtime, 'Confidence threshold').includes(' step="0.0005" '), realtime);
    // Posthoc offers its own detectors: the experimental ONNX hands preset is realtime only.
    assert.deepEqual(optionsOf(rowLabelled(posthoc, 'Skeleton detector')), ['rtmpose', 'mediapipe', 'rtmw_mediapipe_hands', 'dlc']);
});

test('inactive dims every row', () => {
    for (const detector of DETECTORS) {
        for (const rows of ['key', 'all'] as const) {
            const active = detectorRows(detector, rows);
            assert.deepEqual(dimmed(active), [], `${detector} ${rows}`);
            // The same rows stay on screen, each of them dimmed.
            assert.deepEqual(dimmed(detectorRows(detector, rows, {inactive: true})), labels(active), `${detector} ${rows}`);
        }
    }
    assert.deepEqual(dimmed(renderToStaticMarkup(<SkeletonAnchorSetting value="pelvis" onChange={() => {}}/>)), []);
    assert.deepEqual(dimmed(renderToStaticMarkup(<SkeletonAnchorSetting value="pelvis" onChange={() => {}} inactive/>)), ['Skeleton anchor']);
});
