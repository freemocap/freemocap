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
import {
    COMPLEXITY_INFO, CONFIDENCE_INFO, DETECTION_CONFIDENCE_INFO, DETECTOR_INFO, DetectorSettingRows, type DetectorSettingsValue,
    EXECUTION_PROVIDER_INFO, MODEL_INFO, PRESENCE_CONFIDENCE_INFO, TRACKING_CONFIDENCE_INFO,
} from './detector-setting-rows';
import {OutlierRejectionRows} from './outlier-rejection-rows';
import SkeletonAnchorSetting from './skeleton-anchor-setting';

type DetectorRowsProps = Parameters<typeof DetectorSettingRows>[0];
type Handler = (value: string | number | boolean) => void;
interface Info {title: string; text: ReactNode}
interface RowProps {label?: ReactNode; info?: Info; control?: ReactElement<{onChange?: Handler; onToggle?: Handler}>; children?: ReactNode}

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
 * The row with this label, as the element the rows return. The unit runner has no DOM to act in and a row's
 * explanation is not in the markup until it is opened, so the tests below read both from the row's own props.
 */
function rowElement(rows: ReactNode, label: string): RowProps | undefined {
    for (const child of Children.toArray(rows)) {
        if (!isValidElement<RowProps>(child)) continue;
        const found = child.props.label === label ? child.props : rowElement(child.props.children, label);
        if (found) return found;
    }
    return undefined;
}
/** The change handler of the control in the row with this label; the test calls it as the control would. */
function handlerOf(rows: ReactNode, label: string): Handler {
    const control = rowElement(rows, label)?.control;
    const handler = control?.props.onChange ?? control?.props.onToggle;
    assert.ok(handler, `no control with a change handler in a row labelled "${label}"`);
    return handler;
}
/** The explanation behind the info button of the row with this label. */
function infoOf(rows: ReactNode, label: string): Info {
    const info = rowElement(rows, label)?.info;
    assert.ok(info, `no row labelled "${label}"`);
    return info;
}
/** An explanation's text as markup. */
const textOf = (info: Info): string => renderToStaticMarkup(<>{info.text}</>);

/** The posthoc explanation of each detector row. */
const POSTHOC_INFO: Record<string, Info> = {
    'Skeleton detector': DETECTOR_INFO, 'Execution provider': EXECUTION_PROVIDER_INFO, 'Model': MODEL_INFO, 'Pose model size': COMPLEXITY_INFO,
    'Confidence threshold': CONFIDENCE_INFO, 'Detection confidence': DETECTION_CONFIDENCE_INFO, 'Presence confidence': PRESENCE_CONFIDENCE_INFO,
    'Tracking confidence': TRACKING_CONFIDENCE_INFO,
};
/** What today's realtime Skeleton Setup dialog says about the selected detector, word for word. */
const DETECTOR_NOTES: Partial<Record<RealtimeDetectorType, string>> = {
    rtmpose: '133 keypoints (body, hands, face) via YOLOX + RTMW. Uses GPU batched inference when available.',
    mediapipe: 'Body + hands + face via MediaPipe. CPU-only; runs per-camera without GPU batching.',
    rtmw_mediapipe_hands: 'RTMW body and face with cropped MediaPipe hands. The execution provider applies to RTMW; MediaPipe hands run on CPU.',
    rtmw_onnx_hands: 'Experimental RTMW body and face with ONNX palm and hand models. Uses CUDA; CPU is also supported. Compare hand quality with the MediaPipe hands option.',
};
/** And what it says above the confidences of the two presets that add hand detectors to RTMW. */
const HANDS_NOTE = 'The confidence settings below apply to the hands.';

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

test('number fields are named after their rows', () => {
    /** The accessible names of a row's elements of one kind, in order. */
    const names = (row: string, tag: string): (string | undefined)[] =>
        (row.match(new RegExp(`<${tag}[^>]*>`, 'g')) ?? []).map(opening => opening.match(/ aria-label="([^"]*)"/)?.[1]);
    const named = (html: string, label: string, where: string): void => {
        const row = rowLabelled(html, label);
        assert.deepEqual(names(row, 'input'), [label], `${where}: ${row}`);
        // The row's buttons in order: its explanation, then the steppers either side of the field.
        assert.deepEqual(names(row, 'button'), [label, `Decrease ${label}`, `Increase ${label}`], `${where}: ${row}`);
    };
    for (const context of ['posthoc', 'realtime'] as const) {
        const html = detectorRows('rtmw_mediapipe_hands', 'all', {context});
        for (const label of ['Confidence threshold', 'Detection confidence', 'Presence confidence', 'Tracking confidence']) named(html, label, context);
    }
    for (const label of OUTLIER_LIMITS) named(outlierRows(CONFIG), label, 'outlier rejection');
});

test('realtime explanations carry the Skeleton Setup notes', () => {
    const hybrids: RealtimeDetectorType[] = ['rtmw_mediapipe_hands', 'rtmw_onnx_hands'];
    /** The note that ends a realtime row's explanation for this detector, where the dialog has one about that row. */
    const noteFor = (label: string, detector: RealtimeDetectorType): string | undefined =>
        label === 'Skeleton detector' || label === 'Execution provider' ? DETECTOR_NOTES[detector]
            : label.endsWith(' confidence') && hybrids.includes(detector) ? HANDS_NOTE : undefined;
    const shown = new Set<string>();
    for (const detector of DETECTORS) {
        for (const set of ['key', 'all'] as const) {
            const rows = DetectorSettingRows(detectorProps(detector, set));
            for (const label of labels(detectorRows(detector, set)).filter(other => other !== 'DLC model')) {
                const info = infoOf(rows, label), posthoc = POSTHOC_INFO[label], note = noteFor(label, detector);
                assert.equal(info.title, posthoc.title, `${detector} ${set} ${label}`);
                if (note === undefined) {
                    assert.equal(info, posthoc, `${detector} ${set} ${label}`);
                    continue;
                }
                // The row's own explanation, then the note as its last paragraph.
                const own = typeof posthoc.text === 'string' ? `<p>${posthoc.text}</p>` : textOf(posthoc);
                assert.equal(textOf(info), `${own}<p>${note}</p>`, `${detector} ${set} ${label}`);
                shown.add(note);
            }
        }
    }
    // Each of the dialog's five notes has a row: none is left behind with the dialog.
    assert.deepEqual([...shown].sort(), [...Object.values(DETECTOR_NOTES), HANDS_NOTE].sort());

    // The DLC model row says the same in both windows.
    const dlc = infoOf(DetectorSettingRows(detectorProps('dlc', 'all')), 'DLC model');
    assert.equal(dlc.title, 'DLC model');
    assert.equal(textOf(dlc), '<p>The exported DeepLabCut model to run on every camera frame.</p>');
    assert.equal(infoOf(DetectorSettingRows(detectorProps('dlc', 'all', {context: 'posthoc', detectors: DETECTOR_OPTIONS})), 'DLC model'), dlc);
});

test('posthoc explanations are unchanged', () => {
    for (const {value: detector} of DETECTOR_OPTIONS) {
        const posthoc = {context: 'posthoc', detectors: DETECTOR_OPTIONS} as const;
        const rows = DetectorSettingRows(detectorProps(detector, 'all', posthoc));
        const shown = labels(detectorRows(detector, 'all', posthoc)).filter(label => label !== 'DLC model');
        assert.ok(shown.length > 0, detector);
        // The very objects posthoc had before the rows were shared.
        for (const label of shown) assert.equal(infoOf(rows, label), POSTHOC_INFO[label], `${detector} ${label}`);
    }
});
