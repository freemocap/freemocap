import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test('concurrent exports have independent bars and retain a completed sibling', async ({page}) => {
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('http://localhost:53117/');
    const result = await build({stdin: {resolveDir: path.resolve('.'), loader: 'tsx', contents: `
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import Bars from './src/components/pipeline-progress/OperationProgressBars';
        const root = createRoot(document.getElementById('root'));
        const operation = (operation_id, changes={}) => ({operation_id, label:operation_id, status:'running', progress_fraction:null, detail:'', completed:null,total:null,unit:null,elapsed_seconds:42.6,seconds_per_motion_frame:0.0384,...changes});
        window.showCompletedExport = () => root.render(<Bars operations={[
            operation('Save CSV', {status:'complete',progress_fraction:1}), operation('Export Blender')
        ]}/>);
        root.render(<Bars operations={[
            operation('Save CSV',{progress_fraction:0.25,completed:1,total:4,unit:'channels'}),operation('Export Blender')
        ]}/>);
    `}, bundle: true, write: false, format: 'esm', jsx: 'automatic'});
    await page.addScriptTag({content: result.outputFiles[0].text, type: 'module'});
    await expect(page.getByRole('progressbar')).toHaveCount(2);
    await expect(page.getByRole('progressbar', {name: 'Save CSV'})).toHaveAttribute('aria-valuenow', '25');
    await expect(page.getByRole('progressbar', {name: 'Export Blender'})).not.toHaveAttribute('aria-valuenow');
    await expect(page.getByText('1 / 4 channels')).toBeVisible();
    await page.evaluate('window.showCompletedExport()');
    await expect(page.getByRole('progressbar')).toHaveCount(2);
    await expect(page.locator('[data-operation-id="Save CSV"]')).toHaveAttribute('data-status', 'complete');
    await expect(page.locator('[data-operation-id="Export Blender"]')).toHaveAttribute('data-status', 'running');
});


for (const cardWidth of [440, 900]) test(`styled stacked operations remain readable at ${cardWidth}px`, async ({page}, testInfo) => {
    await page.setViewportSize({width: cardWidth + 80, height: 1000});
    await page.route('http://localhost:53117/', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div>'}));
    await page.goto('http://localhost:53117/');
    const result = await build({stdin: {resolveDir: path.resolve('.'), loader: 'tsx', contents: `
        import './src/styles/App.css';
        import React from 'react';
        import {createRoot} from 'react-dom/client';
        import Bars from './src/components/pipeline-progress/OperationProgressBars';
        import Timing from './src/components/pipeline-progress/ProcessingTiming';
        const operation=(operation_id,changes={})=>({operation_id,label:operation_id,status:'running',progress_fraction:null,detail:'',completed:null,total:null,unit:null,elapsed_seconds:42.6,seconds_per_motion_frame:0.0384,...changes});
        createRoot(document.getElementById('root')).render(<div style={{padding:20,background:'#161616',minHeight:'100vh'}}>
          <div className="progress-container flex flex-col gap-2 text-white br-2 m-1 bg-dark pipeline-group-card pipeline-group-card__border-running" style={{width:${cardWidth},padding:16}}>
            <h3 style={{margin:0}}>freemocap_sample_data - Running</h3>
            <Timing timing={{elapsed_seconds:137,motion_frame_count:1108,seconds_per_motion_frame:0.124}} running={false}/>
            <Bars operations={[
              operation('Detect poses and board points in 3 camera videos',{status:'complete',progress_fraction:1,completed:3324,total:3324,unit:'camera images (3 videos x 1,108 frames)'}),
              operation('Triangulate camera observations into 3D points',{status:'complete',progress_fraction:1}),
              operation('Fit skeleton positions and joint rotations',{status:'complete',progress_fraction:1}),
              operation('Save reconstructed motion to Parquet',{status:'complete',progress_fraction:1}),
              operation('Save annotated camera video 1',{status:'complete',progress_fraction:1}),
              operation('Save annotated camera video 2',{status:'complete',progress_fraction:1}),
              operation('Save annotated camera video 3',{status:'complete',progress_fraction:1}),
              operation('Save scientific files (CSV, NPY and NPZ)',{progress_fraction:1/3,completed:5,total:15,unit:'channels',detail:'Writing landmark coordinates and validating saved values.'}),
              operation('Create Blender scene, FBX and BVH files',{detail:'Blender is running in a separate process.'})
            ]}/>
          </div>
        </div>);
    `}, bundle:true,write:false,outdir:'styled-progress',format:'esm',jsx:'automatic',
        loader:{'.svg':'dataurl','.webp':'dataurl','.png':'dataurl','.woff':'dataurl','.woff2':'dataurl','.ttf':'dataurl'},
        external:['/images/*','../images/*','../assets/icons/import-icon.svg']});
    for (const output of result.outputFiles) {
        if(output.path.endsWith('.css')) await page.addStyleTag({content:output.text});
        else await page.addScriptTag({content:output.text,type:'module'});
    }
    await expect(page.getByRole('progressbar')).toHaveCount(9);
    await expect(page.getByText(/Running.*33%/)).toBeVisible();
    await page.screenshot({path:testInfo.outputPath(`stacked-progress-${cardWidth}.png`),fullPage:true});
});