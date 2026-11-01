import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('tall CSV controls use the selected saved run, save, and surface failures', async ({page}, testInfo) => {
    page.on('pageerror', error => {throw error;});
    const bundle = await build({absWorkingDir: process.cwd(), tsconfigRaw: {}, stdin: {contents: `
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import {Provider} from 'react-redux';
        import {store} from './src/store/store';
        import Csv from './src/components/mocap-setup/mocap-csv-settings';
        import SettingsSection from './src/components/common/settings-layout/settings-section';
        import PosthocFilterSettings from './src/components/mocap-setup/mocap-postprocess-settings';
        import './src/index.css';
        createRoot(document.getElementById('root')).render(<Provider store={store}>
            <div className="settings-layout p-2"><SettingsSection title="Post-processing"><PosthocFilterSettings/></SettingsSection>
            <SettingsSection title="Exports"><Csv path="C:/recordings/walk" processing={false} sourceRunId={2}/></SettingsSection></div>
        </Provider>);
    `, resolveDir: process.cwd(), loader: 'tsx'}, bundle: true, write: false, format: 'esm',
        outfile: resolve('.test-artifacts/style-check/panel.js'), external: ['*.svg', '*.png', '*.webp', '*.woff2', '*.woff', '*.ttf'],
        loader: {'.yaml': 'text'}, jsx: 'automatic', alias: {'@': resolve('src')},
        define: {'process.env.NODE_ENV': '"test"', 'import.meta.env': '{}'}});
    let fail = false;
    const requests: unknown[] = [];
    await page.route('**/freemocap/recordings/walk/**', async route => {
        expect(new URL(route.request().url()).searchParams.get('recording_parent_directory')).toBe('C:/recordings');
        if (route.request().method() === 'GET') {
            await route.fulfill({json: {run_ids: [0, 2], selected_run_id: 0, revision: 'revision-a'}});
        } else {
            requests.push(route.request().postDataJSON());
            await route.fulfill({status: fail ? 409 : 202, json: fail ? {detail: 'Recording revision changed; reload the saved result'} :
                {task_id: 'export:csv'}});
        }
    });
    await page.route('**/freemocap/tasks/**', route => route.fulfill({json: {status: 'complete', result:
        {files: ['C:/recordings/walk/exports/walk.tall.csv'], manifest_path: 'C:/recordings/walk/exports/walk.metadata.json'}}}));
    await page.route('http://127.0.0.1:53218/', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('http://127.0.0.1:53218/');
    await page.setViewportSize({width: 720, height: 850});
    await page.addStyleTag({content: bundle.outputFiles.find(file => file.path.endsWith('.css'))!.text});
    await page.addScriptTag({type: 'module', content: bundle.outputFiles.find(file => file.path.endsWith('.js'))!.text});
    const toggle = page.getByRole('switch', {name: 'Save tall CSV after processing'});
    await expect(toggle).not.toBeChecked();
    await toggle.click();
    await expect(toggle).toBeChecked();
    await toggle.click();
    await expect(toggle).not.toBeChecked();
    await expect(page.getByText('Export saved Run 2, selected under Processing stages.')).toBeVisible();
    await page.screenshot({path: testInfo.outputPath('csv-settings.png'), fullPage: true});
    await page.getByRole('button', {name: 'Export now'}).click();
    await expect(page.getByRole('status')).toContainText('walk.tall.csv');
    expect(requests[0]).toEqual({kind: 'tall_csv', run_id: 2, expected_revision: 'revision-a'});
    fail = true;
    await page.getByRole('button', {name: 'Export now'}).click();
    await expect(page.getByRole('alert')).toContainText('Recording revision changed');
    await page.getByRole('button', {name: 'Reload saved results'}).click();
    await expect(page.getByRole('alert')).toHaveCount(0);
});
