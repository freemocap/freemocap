import {createClient} from '../dist/index.js';
import {registerHttpConformance} from '../contracts/http-conformance.mjs';
registerHttpConformance(createClient);

import assert from 'node:assert/strict';
import {test} from 'node:test';
test('explicit hidden utilities preserve their actual server contracts',async()=>{
 const requests=[];
 const client=createClient({baseUrl:'http://server.invalid/prefix',fetch:async(url)=>{requests.push(new URL(url));return new Response('bytes');}});
 const viewer=await client.utilities.playbackViewer();assert.equal(await viewer.data.text(),'bytes');
 const parquet=await client.utilities.parquetByPath('C:/recordings/trial #1/data.parquet');assert.equal(await parquet.data.text(),'bytes');
 assert.equal(requests[0].pathname,'/prefix/freemocap/playback/viewer');
 assert.equal(requests[1].searchParams.get('path'),'C:/recordings/trial #1/data.parquet');
});

test('typed response surface leaves status handling and body consumption to the application',async()=>{
 let sent;
 const client=createClient({baseUrl:'http://server.invalid',fetch:async(_url,init)=>{sent=init;return Response.json({detail:'busy'},{status:409});}});
 const response=await client.responses.shutdown_server_shutdown_post({cache:'no-store',keepalive:true});
 assert.equal(response.status,409);assert.equal(response.bodyUsed,false);assert.equal(sent.keepalive,true);assert.equal(sent.cache,'no-store');
 assert.deepEqual(await response.json(),{detail:'busy'});
});
