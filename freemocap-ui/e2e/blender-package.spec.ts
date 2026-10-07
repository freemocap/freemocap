import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer} from 'node:http';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});
test('package setup and route options reach the export request', async ({page}) => {
    const bundle = await build({bundle: true, write: false, format: 'esm', platform: 'browser',
        alias: {'@': resolve('src')}, loader: {'.yaml': 'text'}, define: {'import.meta.env.DEV': 'false'},
        stdin: {resolveDir: process.cwd(), loader: 'tsx', contents: `
            import React from 'react'; import {createRoot} from 'react-dom/client';
            import {Provider} from 'react-redux'; import {store} from './src/store/store';
            import {BlenderPackageSettings} from './src/components/common/BlenderPackageSettings';
            import {blenderExePathChanged, exportRecordingToBlender} from './src/store/slices/blender';
            import {serverUrls} from './src/constants/server-urls';
            serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
            store.dispatch(blenderExePathChanged('C:/Blender/blender.exe'));
            createRoot(document.getElementById('root')).render(<Provider store={store}><BlenderPackageSettings/>
                <button onClick={()=>store.dispatch(exportRecordingToBlender({recordingFolderPath:'C:/recording'}))}>Test export</button>
            </Provider>);
        `}});
    let exported: any;
    let installed: any;
    const server = createServer(async (request, response) => {
        if (request.url?.includes('/blender/')) {
            let body = ''; for await (const chunk of request) body += chunk;
            const input = JSON.parse(body || '{}');
            response.setHeader('Content-Type', 'application/json');
            if (request.url.endsWith('/inspect')) response.end(JSON.stringify({blender:[5,2,2],python:'3.13',system:'Windows',machine:'AMD64',packages:[]}));
            else if (request.url.endsWith('/addon/install')) {installed=input; response.end(JSON.stringify({package:'bl_ext.freemocap_local.freemocap_blender_addon',success:true}));}
            else {exported=input; response.end(JSON.stringify({success:true,blender_file_path:'C:/recording/recording.blend'}));}
        } else if (request.url === '/entry.js') {
            response.setHeader('Content-Type','text/javascript'); response.end(bundle.outputFiles[0].text);
        } else response.end('<div id="root"></div><script type="module" src="/entry.js"></script>');
    });
    await new Promise<void>(done => server.listen(0,'127.0.0.1',done));
    try {
        const address=server.address(); if (!address || typeof address==='string') throw new Error('Missing address');
        await page.goto(`http://127.0.0.1:${address.port}`);
        await page.getByRole('button',{name:'Check Blender package'}).click();
        await expect(page.getByRole('status')).toContainText('Install a matching');
        await page.getByText('Install bundled add-on ZIP',{exact:true}).click();
        await page.getByLabel('Bundled add-on ZIP path').fill('C:/packages/freemocap.zip');
        await page.getByRole('button',{name:'Install bundled package',exact:true}).click();
        await expect(page.getByRole('status')).toContainText('Installed and verified');
        expect(installed.archivePath).toBe('C:/packages/freemocap.zip');
        await expect(page.getByLabel('Apply foot locking')).toBeDisabled();
        await page.getByLabel('Import route').selectOption('parquet_constraints');
        await page.getByLabel('Apply foot locking').check();
        await page.getByLabel('Blender skeleton rest pose').selectOption('apose');
        await page.getByLabel('FBX',{exact:true}).check();
        await expect(page.getByLabel('BVH',{exact:true})).toBeDisabled();
        await page.getByRole('button',{name:'Test export'}).click();
        await expect.poll(()=>exported?.route).toBe('parquet_constraints');
        expect(exported.package).toBe('bl_ext.freemocap_local.freemocap_blender_addon');
        expect(exported.blenderExportConfig).toMatchObject({formats:['fbx'],rest_pose:'apose',apply_foot_locking:true});
        await page.getByLabel('Import route').selectOption('parquet_segments');
        await expect(page.getByLabel('Apply foot locking')).not.toBeChecked();
        await expect(page.getByLabel('Blender skeleton rest pose')).toHaveValue('tpose');
    } finally {await page.goto('about:blank'); await new Promise<void>(done=>server.close(()=>done()));}
});
