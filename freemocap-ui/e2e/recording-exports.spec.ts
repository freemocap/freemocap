import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer} from 'node:http';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});
for (const settings of ['new', 'historical', 'conflicting']) test(`recording exports select channels, retry and cancel (${settings} settings)`, async ({page}) => {
    const bundle = await build({bundle:true, write:false, outfile:'entry.js', format:'esm', platform:'browser',
        alias:{'@':resolve('src')}, loader:{'.yaml':'text', '.svg':'dataurl'}, define:{'import.meta.env.DEV':'false'},
        stdin:{resolveDir:process.cwd(), loader:'tsx', contents:`
            import React from 'react'; import {createRoot} from 'react-dom/client';
            import {Provider, useSelector} from 'react-redux'; import {store} from './src/store/store';
            import Settings from './src/components/mocap-setup/mocap-export-settings';
            import {serverUrls} from './src/constants/server-urls';
            serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
            function Panel(){const c=useSelector(s=>s.mocap.config); const [run, setRun]=React.useState(3); return <>
              <label>Processing source run<select value={run} onChange={e=>setRun(Number(e.target.value))}><option value="0">0</option><option value="3">3</option></select></label>
              <Settings path="C:/recording" processing={false} sourceRunId={run}/>
              <output style={{display:'none'}} data-testid="preferences">{JSON.stringify({formats:c.exportFormats, data:c.exportChannels, after:c.exportAfterProcessing, tall:c.exportTallCsv})}</output></>}
            createRoot(document.getElementById('root')).render(<Provider store={store}><Panel/></Provider>);
        `}});
    const selections = ['RAW_KEYPOINTS_3D', 'LANDMARKS_3D'].map(channel => ({sensor_group:'cameras',
        source:channel === 'RAW_KEYPOINTS_3D' ? 'tracker' : 'model', reference_frame:'world', channel, static:false}));
    const descriptors = selections.map(selection => ({selection, names:124, components:['x','y','z']}));
    let previewState = 'empty';
    let submitted: any;
    let mode = 'failed';
    let serial = 0;
    const server = createServer(async (request,response) => {
        response.setHeader('Content-Type','application/json');
        if (request.method === 'GET' && request.url?.includes('/export-options')) {
            response.statusCode = previewState === 'error' ? 500 : 200;
            response.end(JSON.stringify(previewState === 'error' ? {detail:'Could not read saved result'} :
                previewState === 'empty' ? {revision:null, selected_run_id:null, runs:[], formats:['wide_csv']} :
                {revision:'snapshot', selected_run_id:3, runs:[{run_id:0,channels:descriptors.slice(0,1)},
                    {run_id:3,channels:descriptors}], formats:['wide_csv']}));
        } else if (request.method === 'POST' && request.url?.startsWith('/freemocap/recordings/recording/exports')) {
            expect(new URL(request.url, 'http://test').searchParams.get('recording_parent_directory')).toBe('C:/');
            let body=''; for await (const chunk of request) body+=chunk; submitted=JSON.parse(body);
            response.statusCode=202; response.end(JSON.stringify({task_id:`export:${++serial}`}));
        } else if (request.url?.includes('/tasks/')) {
            if (request.url.endsWith('/cancel')) mode='cancelled';
            response.end(JSON.stringify({task_id:`export:${serial}`, status:mode,
                progress:{detail:mode === 'failed' ? 'Disk full; retry export' : mode === 'complete' ? 'Wide CSV saved and validated' : mode === 'cancelled' ? 'Export cancelled' : 'Exporting landmarks',
                    progress_fraction:mode==='complete'?1:null},
                result:mode==='complete'?{files:['C:/recording/exports/table.csv'],manifest_path:'C:/recording/exports/recording.wide.metadata.json'}:undefined}));
        } else if (request.url === '/entry.js' || request.url === '/entry.css') {
            const extension=request.url.endsWith('.js')?'.js':'.css';
            response.setHeader('Content-Type', extension==='.js'?'text/javascript':'text/css');
            response.end(bundle.outputFiles.find(file=>file.path.endsWith(extension))!.text);
        } else {
            response.setHeader('Content-Type','text/html');
            response.end('<html><head><link rel="stylesheet" href="/entry.css"></head><body style="background:#0f172a;color:#e2e8f0;font:15px sans-serif;padding:24px;max-width:760px"><div id="root"></div><script type="module" src="/entry.js"></script></body></html>');
        }
    });
    await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
    try {
        if (settings !== 'new') await page.addInitScript(kind => localStorage.setItem('freemocap:mocap.config', JSON.stringify(
            kind === 'historical' ? {scientificExportFormats:['npz'], scientificExportData:['LANDMARKS_3D'], scientificExportAfterProcessing:true}
                : {scientificExportFormats:['wide_csv'], exportFormats:['npz']}
        )), settings);
        await page.goto(`http://127.0.0.1:${(server.address() as any).port}`);
        if (settings === 'conflicting') {
            await expect(page.getByRole('alert')).toContainText('Saved export settings conflict');
            expect(await page.evaluate(() => JSON.parse(localStorage.getItem('freemocap:mocap.config')!).scientificExportFormats)).toEqual(['wide_csv']);
            await page.getByRole('button', {name:'Reset export settings'}).click();
        }
        const save = page.getByRole('button',{name:'Export saved result',exact:true});
        const npy = page.getByRole('checkbox', {name:'NumPy NPY arrays (optional)', exact:true});
        const npz = page.getByRole('checkbox', {name:'NumPy NPZ archive', exact:true});
        await expect(npy).not.toBeChecked();
        if (settings === 'historical') {await expect(npz).toBeChecked(); await npz.uncheck();}
        await expect(npz).not.toBeChecked();
        if (settings === 'historical') {
            await expect(page.getByLabel('Export selected formats after processing')).toBeChecked();
            await page.getByLabel('Export selected formats after processing').uncheck();
        }
        await expect(page.getByLabel('Export selected formats after processing')).not.toBeChecked();
        await expect(page.getByText('NPZ packages the dataset in one archive.', {exact:false})).toBeVisible();
        await expect(page.getByText('multiple array files and dataset.json in npy/', {exact:false})).toBeVisible();
        await expect(page.getByText('one shared .frames', {exact:false})).toHaveCount(0);
        await expect(page.getByRole('checkbox', {name:'2D keypoints - camera observations', exact:true})).toBeVisible();
        await expect(page.getByText('No saved result yet.', {exact:false}).first()).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
        await expect(save).toBeDisabled();
        await page.getByText('Tall CSV diagnostic export', {exact:true}).click();
        await expect(page.getByText('No saved result yet.', {exact:false})).toHaveCount(2);
        await expect(page.getByRole('button', {name:'Export now', exact:true})).toBeDisabled();
        previewState = 'error';
        await page.getByRole('button', {name:'Reload saved results', exact:true}).click();
        await expect(page.getByRole('alert')).toContainText('Could not read saved result');
        previewState = 'ready';
        await page.getByRole('button', {name:'Reload saved results', exact:true}).click();
        await expect(page.getByLabel('Processing source run')).toHaveValue('3');
        await expect(page.getByRole('alert')).toHaveCount(0);
        await page.getByText('Tall CSV diagnostic export', {exact:true}).click();
        await expect(page.getByLabel('Wide CSV',{exact:true})).not.toBeChecked();
        await page.getByLabel('Wide CSV',{exact:true}).check();
        await expect(save).toBeEnabled();
        await npy.check();
        await expect(page.getByTestId('preferences')).toContainText('"formats":["wide_csv","npy"]');
        await expect(page.getByText('At least', {exact:false})).toHaveCount(0);
        await npy.uncheck();
        const raw=page.getByRole('checkbox',{name:'3D keypoints - raw triangulated',exact:true});
        const landmarks=page.getByRole('checkbox',{name:'3D landmarks',exact:true});
        await expect(raw).not.toBeChecked();
        await expect(landmarks).toBeChecked();
        await expect(page.getByRole('checkbox',{name:/Rigid-body segments/})).not.toBeChecked();
        await landmarks.uncheck();
        await expect(save).toBeDisabled();
        await landmarks.check();
        await page.getByLabel('Processing source run').selectOption('0');
        await expect(page.getByRole('alert')).toContainText('unavailable');
        await expect(save).toBeDisabled();
        await page.getByLabel('Processing source run').selectOption('3');
        await page.getByLabel('Export selected formats after processing').check();
        await save.click();
        await expect(page.getByRole('alert')).toContainText('Disk full');
        expect(submitted).toEqual({kind:'channels',run_id:3,expected_revision:'snapshot',formats:['wide_csv'],data:['LANDMARKS_3D'],keep:false});
        mode='complete'; await npz.check(); await save.click();
        await expect(page.getByText('Saved and validated 1 file.',{exact:false})).toBeVisible();
        expect(submitted.formats).toEqual(['wide_csv', 'npz']);
        await expect(npy).not.toBeChecked();
        await expect(page.getByTestId('preferences')).toContainText('"after":true');
        await expect(page.getByTestId('preferences')).toContainText('"tall":false');
        await page.screenshot({path:'../.test-artifacts/wide-csv/panel.png',fullPage:true});
        mode='running'; await save.click();
        await expect(page.getByRole('button',{name:'Cancel export'})).toBeEnabled();
        await page.getByRole('button',{name:'Cancel export'}).click();
        await expect(page.getByText('Export cancelled', {exact:false})).toBeVisible();
        await expect.poll(() => page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('freemocap:mocap.config')!)).some(key => key.startsWith('scientific')))).toBe(false);
    } finally {
        await page.close();
        await new Promise<void>(resolve => {
            server.close(() => resolve());
            server.closeAllConnections();
        });
    }
});
