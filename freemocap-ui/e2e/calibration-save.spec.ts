import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';
import {calibrationFixture} from './fixtures/calibration';
import {CalibrationUpdateRequestSchema} from '../src/store/slices/calibration/calibration-types';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

for (const success of [true, false]) {
    test(`calibration save ${success ? 'consumes' : 'preserves'} the runtime offset`, async ({page}) => {
        page.on('pageerror', error => {throw error;});
        let saves = 0;
        let applies = 0;
        await page.route('**/freemocap/realtime/apply', async route => {
            applies++;
            await route.fulfill({json: {camera_group_id: 'cameras', pipeline_id: 'live'}});
        });
        await page.route('**/calibration/transform', async route => {
            saves++;
            const request = CalibrationUpdateRequestSchema.parse(route.request().postDataJSON());
            expect(request.path).toBe('C:/calibration.toml');
            expect(request.expected_mtime_ms).toBe(1);
            expect(request.transformations).toEqual([{
                operation: 'manual',
                quaternion_wxyz: [1, 0, 0, 0],
                translation_mm: [10, 20, 30],
            }]);
            if (!success) {
                await route.fulfill({status: 422, json: {detail: 'File busy'}});
                return;
            }
            const saved = calibrationFixture(request.path);
            saved.mtimeMs = 2;
            saved.cameras[0].world_position = [20, -10, 30];
            saved.cameras[0].extrinsics.translation = [-20, 10, -30];
            saved.metadata.transformation_history = request.transformations;
            await route.fulfill({json: saved});
        });
        await page.route('http://localhost:53117/', route => route.fulfill({
            contentType: 'text/html', body: '<div id="root"></div>',
        }));
        await page.goto('http://localhost:53117/');
        const bundle = await build({
            stdin: {contents: `
                import React from 'react';
                import {createRoot} from 'react-dom/client';
                import {Provider} from 'react-redux';
                import {store, useAppSelector} from './src/store';
                import {calibrationFixture} from './e2e/fixtures/calibration';
                import {calibrationLoadedFromBundle} from './src/store/slices/calibration';
                import {pipelineConfigUpdated} from './src/store/slices/realtime/realtime-slice';
                import {applyRealtimePipeline} from './src/store/slices/realtime/realtime-thunks';
                import Controls from './src/components/pipeline-progress/calibration-progress/calibration-reference-frame';
                import {useReferenceFrameForwarder} from './src/components/viewport3d/hooks/useReferenceFrameForwarder';
                import type {CalibrationScene} from './src/store/slices/calibration/calibration-types';
                store.dispatch(calibrationLoadedFromBundle(calibrationFixture('C:/calibration.toml')));
                const config = structuredClone(store.getState().realtime.pipelineConfig);
                config.aggregator_config.calibration_toml_path = 'C:/calibration.toml';
                config.aggregator_config.reference_transform = {
                    matrix: [1,0,0,10,0,1,0,20,0,0,1,30,0,0,0,1],
                };
                store.dispatch(pipelineConfigUpdated(config));
                store.dispatch(applyRealtimePipeline.fulfilled(
                    {camera_group_id: 'cameras', pipeline_id: 'live'}, 'setup', config,
                ));
                const target = {
                    postMessage(message: {type: 'calibrationScene'; data: CalibrationScene}) {
                        if (message.data.calibration?.mtimeMs === 2 && message.data.referenceTransform !== null) {
                            throw new Error('Saved geometry was forwarded with the old runtime offset');
                        }
                    },
                };
                function Harness() {
                    const calibration = useAppSelector(state => state.calibration.loadedCalibration);
                    const offset = useAppSelector(state => state.realtime.pipelineConfig.aggregator_config.reference_transform);
                    useReferenceFrameForwarder(target, true, calibration);
                    return <>
                        <Controls calibrationPath={calibration?.path ?? null}/>
                        <output aria-label="Saved revision">{calibration?.mtimeMs}</output>
                        <output aria-label="Runtime offset">{offset ? 'active' : 'none'}</output>
                        <output aria-label="History entries">{calibration?.metadata.transformation_history.length}</output>
                    </>;
                }
                createRoot(document.getElementById('root')!).render(
                    <Provider store={store}><Harness/></Provider>,
                );
            `, resolveDir: path.resolve('.'), loader: 'tsx'},
            bundle: true, write: false, outdir: 'calibration-save-test-bundle',
            format: 'esm', jsx: 'automatic',
            loader: {'.yaml': 'text'}, alias: {'@': path.resolve('src')},
            plugins: [{name: 'omit-webgl-preview', setup(builder) {
                builder.onLoad({filter: /transform-preview\.tsx$/}, () => ({
                    contents: 'export default function Preview() { return null; }', loader: 'tsx',
                }));
            }}],
        });
        for (const file of bundle.outputFiles) {
            if (file.path.endsWith('.css')) await page.addStyleTag({content: file.text});
            else await page.addScriptTag({content: file.text, type: 'module'});
        }
        await page.getByRole('button', {name: 'Apply to calibration file', exact: true}).click();
        await expect(page.getByLabel('Saved revision')).toHaveText(success ? '2' : '1');
        await expect(page.getByLabel('Runtime offset')).toHaveText(success ? 'none' : 'active');
        await expect(page.getByLabel('History entries')).toHaveText(success ? '1' : '0');
        if (success) {
            await expect(page.getByLabel('Runtime transformation')).toHaveCount(0);
            await expect(page.getByRole('button', {name: 'Apply to calibration file', exact: true})).toBeDisabled();
        } else {
            await expect(page.getByLabel('Runtime transformation')).toContainText('[10, 20, 30]');
            await expect(page.getByRole('alert')).toContainText('File busy');
        }
        expect(saves).toBe(1);
        expect(applies).toBe(0);
    });
}
