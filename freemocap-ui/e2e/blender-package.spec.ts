import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer} from 'node:http';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});
test('package setup and route options reach the export request', async ({page}) => {
    const bundle = await build({bundle: true, write: false, outfile: 'entry.js', format: 'esm', platform: 'browser',
        external: ['*.svg'], alias: {'@': resolve('src')}, loader: {'.yaml': 'text', '.svg': 'dataurl'}, define: {'import.meta.env.DEV': 'false'},
        stdin: {resolveDir: process.cwd(), loader: 'tsx', contents: `
            import React from 'react'; import {createRoot} from 'react-dom/client';
            import './src/styles/icons.css'; import './src/styles/toggle.css';
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
    const packageName = 'bl_ext.freemocap_local.freemocap_blender_addon';
    const sourceHash = '1'.repeat(64);
    const server = createServer(async (request, response) => {
        if (request.url?.includes('/blender/')) {
            let body = ''; for await (const chunk of request) body += chunk;
            const input = JSON.parse(body || '{}');
            response.setHeader('Content-Type', 'application/json');
            if (request.url.endsWith('/inspect')) {
                const ready = !!installed && input.developmentBuildHash === sourceHash;
                response.end(JSON.stringify({blender:[5,2,2],python:'3.13',system:'Windows',machine:'AMD64',packages:[packageName],
                    expected:{version:'2026.4.1041',source_commit:'expected',source_sha256:'0'.repeat(64)},
                    package_details:[{package:packageName,version:'2026.4.1041',ready,
                        identity:installed ? {version:'2026.4.1041',source_commit:'local',source_sha256:sourceHash,source_dirty:true,export_api_version:1,package_format:'extension'} : null,
                        dependencies:installed ? {pyarrow:'25.0.1'} : null,
                        build_match: ready ? 'development' : installed ? 'different' : 'unverified',
                        errors: ready ? [] : installed ? ['Installed add-on differs from the expected build.'] : ['Missing pyarrow in Blender.']}]}));
            }
            else if (request.url.endsWith('/addon/install')) {installed=input; response.end(JSON.stringify({package:'bl_ext.freemocap_local.freemocap_blender_addon',success:true}));}
            else {exported=input; response.end(JSON.stringify({success:true,blender_file_path:'C:/recording/recording.blend'}));}
        } else if (request.url === '/entry.js') {
            response.setHeader('Content-Type','text/javascript'); response.end(bundle.outputFiles.find(file => file.path.endsWith('.js'))!.text);
        } else if (request.url === '/entry.css') {
            response.setHeader('Content-Type','text/css'); response.end(bundle.outputFiles.find(file => file.path.endsWith('.css'))!.text);
        } else {
            response.setHeader('Content-Type','text/html');
            response.end('<link rel="stylesheet" href="/entry.css"><div id="root"></div><script type="module" src="/entry.js"></script>');
        }
    });
    await new Promise<void>(done => server.listen(0,'127.0.0.1',done));
    try {
        const address=server.address(); if (!address || typeof address==='string') throw new Error('Missing address');
        await page.goto(`http://127.0.0.1:${address.port}`);
        await expect(page.getByText('Add-on setup is automatic.', {exact:false})).toBeVisible();
        await page.getByText('Advanced package diagnostics and development', {exact:true}).click();
        await page.getByRole('button',{name:'Check package',exact:true}).click();
        await expect(page.getByText('Missing pyarrow in Blender.',{exact:true})).toBeVisible();
        await expect(page.getByText('Selected package verified for export.',{exact:false})).toHaveCount(0);
        await page.getByLabel('Bundled add-on ZIP path').fill('C:/packages/freemocap.zip');
        await page.getByRole('button',{name:'Install bundled package',exact:true}).click();
        await expect(page.getByText('Installed add-on differs from the expected build.',{exact:true})).toBeVisible();
        await page.getByRole('button',{name:'Use this exact build for development'}).click();
        await expect(page.getByRole('status')).toContainText('Selected package verified for export.');
        expect(installed.archivePath).toBe('C:/packages/freemocap.zip');
        await expect(page.getByRole('switch',{name:'Foot locking',exact:true})).toBeDisabled();
        await page.getByRole('combobox',{name:'Import route',exact:true}).selectOption('parquet_constraints');
        await page.getByRole('switch',{name:'Foot locking',exact:true}).click();
        await page.getByRole('combobox',{name:'Rest pose',exact:true}).selectOption('apose');
        await page.getByRole('switch',{name:'Export FBX',exact:true}).click();
        await expect(page.getByRole('switch',{name:'Export BVH',exact:true})).toBeDisabled();
        await page.getByRole('button',{name:'Test export'}).click();
        await expect.poll(()=>exported?.route).toBe('parquet_constraints');
        expect(exported.package).toBe('bl_ext.freemocap_local.freemocap_blender_addon');
        expect(exported.developmentBuildHash).toBe(sourceHash);
        expect(exported.blenderExportConfig).toMatchObject({formats:['fbx'],rest_pose:'apose',apply_foot_locking:true});
        await page.getByRole('combobox',{name:'Import route',exact:true}).selectOption('parquet_segments');
        await expect(page.getByRole('switch',{name:'Foot locking',exact:true})).not.toBeChecked();
        await expect(page.getByRole('combobox',{name:'Rest pose',exact:true})).toHaveValue('tpose');
        await page.getByRole('button',{name:'Use expected build',exact:true}).click();
        await expect(page.getByText('Installed add-on differs from the expected build.',{exact:true})).toBeVisible();
    } finally {server.closeAllConnections(); await new Promise<void>(done=>server.close(()=>done()));}
});
