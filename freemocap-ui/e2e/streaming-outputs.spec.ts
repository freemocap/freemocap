import {test, expect, type Page} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';
const capabilities = [{protocol:'vmc',available:true,overflow_policy:'latest',config_schema:{properties:{host:{type:'string',default:'127.0.0.1'},port:{type:'integer',default:39539},model_id:{type:'string',default:'standard_human'}}}}, {protocol:'lsl',available:false,unavailable_reason:'LSL runtime missing',config_schema:{}}];
const output = {id:'out-a',protocol:'vmc',status:'idle',pipeline_id:'source-a',config:{},queue_capacity:8,overflow_policy:'latest',frames_emitted:0,source_frame_gaps:0,queue_dropped_frames:0,queue_overflows:0};
async function mount(page:Page) {
 await page.route('http://localhost:53117/',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
 await page.goto('http://localhost:53117/');
 const bundle=await build({stdin:{contents:`
 import React from 'react';import {createRoot} from 'react-dom/client';
 import {StreamingOutputsPanel} from './src/components/control-panels/streaming-outputs/StreamingOutputsPanel';
 import {serverUrls} from './src/constants/server-urls';
 window.changeServer=()=>serverUrls.setPort(53118);
 createRoot(document.getElementById('root')).render(<React.StrictMode><StreamingOutputsPanel/></React.StrictMode>);
 `,resolveDir:path.resolve('.'),loader:'tsx'},bundle:true,write:false,format:'esm',alias:{'@':path.resolve('src')}});
 await page.addScriptTag({content:bundle.outputFiles[0].text,type:'module'});
 await page.getByRole('button',{name:/Streaming outputs/}).click();
}
test('HTTP controls create idle output, observe emission and stop without a viewer socket',async({page})=>{
 let states:typeof output[]=[];let submitted:unknown;
 await page.route('http://localhost:53117/freemocap/streaming/**',async route=>{
  const request=route.request();
  if(request.url().endsWith('/protocols'))return route.fulfill({json:capabilities});
  if(request.method()==='POST'){submitted=request.postDataJSON();states=[{...output}];return route.fulfill({status:201,json:states[0]});}
  if(request.method()==='DELETE'){states=[{...states[0],status:'stopped'}];return route.fulfill({json:states[0]});}
  return route.fulfill({json:states});
 });
 await mount(page);
 await expect(page.getByLabel('Host',{exact:true})).toHaveValue('127.0.0.1');
 await page.getByLabel('Host',{exact:true}).fill('192.0.2.20');
 await page.getByLabel('Port',{exact:true}).fill('39540');
 await page.getByLabel('Source pipeline ID').fill('source-a');
 await page.getByRole('button',{name:'Start output'}).click();
 await expect(page.getByTestId('output-state')).toHaveText('idle');
 expect(submitted).toEqual({protocol:'vmc',pipeline_id:'source-a',queue_capacity:8,config:{host:'192.0.2.20',port:39540,model_id:'standard_human'}});
 states=[{...output,status:'running',frames_emitted:17}];
 await expect(page.getByTestId('output-state')).toHaveText('running');
 await expect(page.getByText(/Frames emitted: 17/)).toBeVisible();
 await page.getByRole('button',{name:'Stop output'}).click();
 await expect(page.getByTestId('output-state')).toHaveText('stopped');
 await page.getByLabel('Protocol',{exact:true}).selectOption('lsl');
 await expect(page.getByText('LSL runtime missing')).toBeVisible();
 await expect(page.getByRole('button',{name:'Start output'})).toBeDisabled();
});
test('unreachable status stays uncertain; changing server discards previous outputs',async({page})=>{
 let broken=false;
 await page.route('http://localhost:53117/freemocap/streaming/**',route=>broken?route.abort():route.fulfill({json:route.request().url().endsWith('/protocols')?capabilities:[{...output,status:'running'}]}));
 await page.route('http://localhost:53118/freemocap/streaming/**',route=>route.fulfill({json:route.request().url().endsWith('/protocols')?capabilities:[]}));
 await mount(page);
 await expect(page.getByTestId('output-state')).toHaveText('running');broken=true;
 await expect(page.getByRole('alert')).toContainText('Outputs may still be running');
 await expect(page.getByTestId('output-state')).toHaveText('running');
 await expect(page.getByRole('button',{name:'Stop output'})).toBeDisabled();
 await page.getByLabel('Source pipeline ID').fill('old-server-source');
 await page.evaluate(()=>(window as unknown as {changeServer:()=>void}).changeServer());
 await expect(page.getByTestId('output-state')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Start output'})).toBeEnabled();
 await expect(page.getByLabel('Source pipeline ID')).toHaveValue('');
});

test('late polling cannot overwrite stop and server errors retain their explanation',async({page})=>{
 let polls=0;let release:(()=>void)|undefined;let stopped=false;let holdNext=false;
 await page.route('http://localhost:53117/freemocap/streaming/**',async route=>{
  const request=route.request();
  if(request.url().endsWith('/protocols'))return route.fulfill({json:capabilities});
  if(request.method()==='DELETE'){stopped=true;return route.fulfill({json:{...output,status:'stopped'}});}
  if(request.method()==='POST')return route.fulfill({status:409,json:{detail:'Select pipeline_id when multiple sources are active'}});
  polls++;
  if(holdNext && !release){await new Promise<void>(resolve=>{release=resolve;});await route.fulfill({json:[{...output,status:'running'}]}).catch(()=>{});return;}
  return route.fulfill({json:[{...output,status:stopped?'stopped':'running'}]});
 });
 await mount(page);
 await expect(page.getByTestId('output-state')).toHaveText('running');
 holdNext=true;
 await expect.poll(()=>Boolean(release)).toBe(true);
 await page.getByRole('button',{name:'Stop output'}).click();
 await expect(page.getByTestId('output-state')).toHaveText('stopped');const heldPoll= polls;release!();
 await expect.poll(()=>polls).toBeGreaterThan(heldPoll);
 await expect(page.getByTestId('output-state')).toHaveText('stopped');
 await page.getByRole('button',{name:'Start output'}).click();
 await expect(page.getByRole('alert')).toContainText('Select pipeline_id when multiple sources are active');
});
