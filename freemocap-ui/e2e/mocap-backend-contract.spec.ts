import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {execFileSync} from 'node:child_process';
import path from 'node:path';

test('characterize UI defaults and DLC export conflict at the backend config boundary', async ({page}, info) => {
    const requests: any[] = [];
    await page.route('http://localhost:53117/**', async route => {
        if (route.request().method() === 'POST') {
            requests.push(route.request().postDataJSON());
            await route.fulfill({json: {success:true, task_id:'diagnostic'}});
        } else await route.fulfill({json: {server_instance_id:'11111111-1111-4111-8111-111111111111',revision:0,recording_owners:[],tasks:[]}});
    });
    await page.route('http://localhost:53117/', route => route.fulfill({contentType:'text/html',body:'<output id="result"></output>'}));
    await page.goto('http://localhost:53117/');
    const bundle = await build({stdin:{resolveDir:path.resolve('.'),loader:'ts',contents:`
        import {store} from './src/store/store';
        import {activeRecordingSet} from './src/store/slices/active-recording/active-recording-slice';
        import {mocapDetectorTypeChanged, mocapDlcSettingsChanged} from './src/store/slices/mocap/mocap-slice';
        import {processMocapRecording} from './src/store/slices/mocap/mocap-thunks';
        async function run() {
            store.dispatch(activeRecordingSet({baseDirectory:'/recordings',recordingName:'baseline',origin:'browsed'}));
            await store.dispatch(processMocapRecording()).unwrap();
            store.dispatch(mocapDetectorTypeChanged('dlc'));
            store.dispatch(mocapDlcSettingsChanged({dlcModelPath:'/models/diagnostic.onnx'}));
            await store.dispatch(processMocapRecording()).unwrap();
            document.getElementById('result')!.textContent='done';
        }
        void run().catch(error => {document.getElementById('result')!.textContent=String(error)});
    `},bundle:true,write:false,outdir:'contract-test',format:'esm',loader:{'.yaml':'text'},alias:{'@':path.resolve('src')}});
    for (const file of bundle.outputFiles) {
        if (file.path.endsWith('.css')) await page.addStyleTag({content:file.text});
        else await page.addScriptTag({content:file.text,type:'module'});
    }
    await expect(page.locator('#result')).toHaveText('done');
    expect(requests).toHaveLength(2);
    const python = process.env.FREEMOCAP_TEST_PYTHON ?? path.resolve('../../freemocap/.venv/bin/python');
    const output = execFileSync(python, ['-B','-c', `
import json, sys
from pydantic import ValidationError
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
requests=json.load(sys.stdin)
result={'backend_default': PosthocMocapPipelineConfig().rtmpose_confidence_threshold}
result['ui_effective']=PosthocMocapPipelineConfig.model_validate(requests[0]['config']).rtmpose_confidence_threshold
try:
    PosthocMocapPipelineConfig.model_validate(requests[1]['config'])
    result['dlc_error']=None
except ValidationError as error:
    result['dlc_error']=str(error)
print(json.dumps(result))
`], {input:JSON.stringify(requests),encoding:'utf8'});
    const result=JSON.parse(output.trim().split('\n').at(-1)!);
    await info.attach('actual-ui-requests',{body:JSON.stringify(requests,null,2),contentType:'application/json'});
    await info.attach('backend-validation',{body:JSON.stringify(result,null,2),contentType:'application/json'});
    expect(result.ui_effective).toBe(0.004);
    expect(result.backend_default).toBe(0.4);
    // Characterization of the reported defect, not certification of DLC processing.
    expect(requests[1].config.exportOptions.data).toEqual(['LANDMARKS_3D']);
    expect(requests[1].config.scientificExports).toEqual({formats:[],data:[]});
    expect(result.dlc_error).toContain('Conflicting export options in saved settings: exportOptions, scientificExports');
});
