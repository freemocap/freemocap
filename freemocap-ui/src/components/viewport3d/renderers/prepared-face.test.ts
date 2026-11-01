import assert from 'node:assert/strict';
import test from 'node:test';
import {ModelDefinitionSchema} from '@/services/server/transport/message-contract';
import {prepareFace, writeFace} from './prepared-face';
const model = (edges: string[][]) => ModelDefinitionSchema.parse({model_id:'human', segments:[], landmarks:[], connections:[], tracker_connections:edges});

test('declared face topology supports current names, reordered layouts and missing rows without guessed edges', () => {
    const m = model([['face_0000','face_0017'],['face_0017','face_0033'],['body','face_0000'],['face_0000','absent'],['face_0017','face_0000']]);
    const p = prepareFace(['face_0033','body','face_0000','face_0017'], [m]);
    assert.deepEqual([...p.points],[0,2,3]); assert.deepEqual([...p.edges],[2,3,3,0]);
    assert.deepEqual([...prepareFace(['face_0017','face_0000'],[m]).edges],[1,0]);
    assert.equal(prepareFace(['face_0000','face_0017'],[model([])]).edges.length,0);
    assert.deepEqual([...prepareFace(['face_0','face_1'],[model([['face_0','face_1']])]).edges],[0,1]);
});

test('dirty numeric updates reuse output and compact invalid endpoints without retaining prior points', () => {
    const rows=Int32Array.from([0,1,1,2]), output=new Float32Array(12), buffer=output.buffer;
    const data=Float32Array.from([1,2,3,4,5,6,7,8,9]);
    for(let i=0;i<1000;i++) assert.equal(writeFace(data,rows,output,true),2);
    assert.equal(output.buffer,buffer);
    assert.deepEqual([...output],[1,2,3,4,5,6,4,5,6,7,8,9]);
    data[0]=NaN;
    assert.equal(writeFace(data,rows,output,true),1);
    assert.deepEqual([...output.slice(0,6)],[4,5,6,7,8,9]);
    data.fill(NaN); assert.equal(writeFace(data,rows,output,true),0);
    assert.equal(writeFace(new Float32Array(),rows,output,true),0);
});
