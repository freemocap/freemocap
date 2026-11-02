/** Reusable SDK tests. Bind registerHttpConformance(createClient) in SDK tests.
 * Expected commands/values below are authored from W3's accepted handoff, independently
 * of the SDK request builder. Inventory iteration is coverage, not a behavioral oracle.
 */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
const contract=JSON.parse(readFileSync(new URL('./operations.json',import.meta.url),'utf8'));
const id=(method,path)=>{const entry=contract.public_http.find(r=>r.method===method&&r.path===path);assert.ok(entry);return entry.operation_id;};
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
export function registerHttpConformance(createClient){
 for(const operation of contract.public_http){
  test('HTTP method/path binding: '+operation.method+' '+operation.path,async()=>{
   let observed;
   const client=createClient({baseUrl:'http://example.invalid',fetch:async(url,init)=>{observed=[new URL(url).pathname,init.method];return json({});}});
   const path=Object.fromEntries([...operation.path.matchAll(/\{([^}]+)\}/g)].map(([,key])=>[key,key==='run_id'?3:'sample #1']));
   await client.operations[operation.operation_id]({path,body:operation.method==='GET'?undefined:{}});
   const expected=operation.path.replace(/\{([^}]+)\}/g,(_,key)=>encodeURIComponent(String(path[key])));
   assert.deepEqual(observed,[expected,operation.method]);
  });
 }

 test('all reviewed public operations have callable SDK bindings',()=>{
  const client=createClient({baseUrl:'http://example.invalid',fetch:async()=>json({})});
  for(const op of contract.public_http)assert.equal(typeof client.operations[op.operation_id],'function',op.operation_id);
 });
 test('recording ID and alternate parent are encoded separately and absence is omitted',async()=>{
  const seen=[];const client=createClient({baseUrl:'http://example.invalid/prefix',fetch:async(url,init)=>{seen.push([String(url),init]);return json({});}});
  const call=client.operations[id('GET','/freemocap/recordings/{recording_id}')];
  await call({path:{recording_id:'trial #1'},query:{recording_parent_directory:'C:/data/other parent'}});
  const url=new URL(seen[0][0]);assert.equal(url.pathname,'/prefix/freemocap/recordings/trial%20%231');
  assert.equal(url.searchParams.get('recording_parent_directory'),'C:/data/other parent');
  await call({path:{recording_id:'trial'}});assert.equal(new URL(seen[1][0]).search,'');
 });
 test('shutdown and camera stop use POST; pause uses explicit PUT false',async()=>{
  const seen=[];const client=createClient({baseUrl:'http://example.invalid',fetch:async(url,init)=>{seen.push([new URL(url).pathname,init]);return json({});}});
  await client.operations[id('POST','/shutdown')]();
  await client.operations[id('POST','/skellycam/camera/group/all/record/stop')]();
  await client.operations[id('PUT','/skellycam/camera/group/all/pause')]({body:{paused:false}});
  assert.deepEqual(seen.map(([p,i])=>[p,i.method]),[['/shutdown','POST'],['/skellycam/camera/group/all/record/stop','POST'],['/skellycam/camera/group/all/pause','PUT']]);
  assert.deepEqual(JSON.parse(seen[2][1].body),{paused:false});
 });
 test('export acceptance preserves typed request and task reference rather than claiming completion',async()=>{
  let request;const client=createClient({baseUrl:'http://example.invalid',fetch:async(url,init)=>{request=init;return json({task_id:'export:7',status_url:'/freemocap/tasks/export:7'},202);}});
  const result=await client.operations[id('POST','/freemocap/recordings/{recording_id}/exports')]({path:{recording_id:'trial'},body:{kind:'tall_csv',run_id:3,expected_revision:'rev-a'}});
  assert.deepEqual(JSON.parse(request.body),{kind:'tall_csv',run_id:3,expected_revision:'rev-a'});
  assert.equal(result.status,202);assert.equal(result.data.task_id,'export:7');assert.equal(result.data.status,undefined);
 });
 test('busy/stale errors preserve status and details and do not retry stateful requests',async()=>{
  let attempts=0;const client=createClient({baseUrl:'http://example.invalid',fetch:async()=>{attempts++;return json({detail:{code:'recording_busy',owner:{task_id:'mocap:1'}}},409);}});
  await assert.rejects(client.operations[id('POST','/freemocap/recordings/{recording_id}/exports')]({path:{recording_id:'trial'},body:{kind:'tall_csv'}}),error=>error.status===409&&error.body.detail.code==='recording_busy');
  assert.equal(attempts,1);
 });
 test('task cancellation is explicit and pending cancellation remains pending',async()=>{
  const seen=[];const client=createClient({baseUrl:'http://example.invalid',fetch:async(url,init)=>{seen.push([new URL(url).pathname,init.method]);return json({task_id:'export:7',status:'running',cancellation_requested:true});}});
  const result=await client.operations[id('POST','/freemocap/tasks/{task_id}/cancel')]({path:{task_id:'export:7'}});
  assert.deepEqual(seen,[['/freemocap/tasks/export%3A7/cancel','POST']]);assert.equal(result.data.status,'running');
 });
 test('request abort is forwarded without issuing a task-cancel command',async()=>{
  const controller=new AbortController();let calls=0;
  const client=createClient({baseUrl:'http://example.invalid',fetch:async(url,init)=>{calls++;assert.equal(init.signal,controller.signal);throw new DOMException('Aborted','AbortError');}});
  controller.abort();await assert.rejects(client.operations[id('GET','/freemocap/tasks')]({signal:controller.signal}),{name:'AbortError'});assert.equal(calls,1);
 });
 test('binary video ranges retain response headers and bytes rather than JSON decoding',async()=>{
  let headers;const client=createClient({baseUrl:'http://example.invalid',fetch:async(url,init)=>{headers=new Headers(init.headers);return new Response(new Uint8Array([1,2,3]),{status:206,headers:{'Content-Type':'video/mp4','Content-Range':'bytes 0-2/10'}});}});
  const result=await client.operations[id('GET','/freemocap/recordings/{recording_id}/videos/{video_id}')]({path:{recording_id:'trial',video_id:'cam.mp4'},headers:{Range:'bytes=0-2'}});
  assert.equal(headers.get('Range'),'bytes=0-2');assert.equal(result.status,206);assert.equal(result.headers.get('Content-Range'),'bytes 0-2/10');
  assert.deepEqual([...new Uint8Array(await result.data.arrayBuffer())],[1,2,3]);
 });
 test('empty 204 responses are not parsed as JSON',async()=>{
  const client=createClient({baseUrl:'http://example.invalid',fetch:async()=>new Response(null,{status:204})});
  const result=await client.operations[id('POST','/freemocap/realtime/reset-skeleton-fitter')]();assert.equal(result.data,undefined);
 });
 test('network failure does not automatically replay an unsafe command',async()=>{
  let attempts=0;const client=createClient({baseUrl:'http://example.invalid',fetch:async()=>{attempts++;throw new TypeError('network unavailable');}});
  await assert.rejects(client.operations[id('POST','/shutdown')](),TypeError);assert.equal(attempts,1);
 });
}

