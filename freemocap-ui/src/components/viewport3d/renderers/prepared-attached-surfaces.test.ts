import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Group, Vector3} from 'three';
import {ModelDefinitionSchema} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {prepareModels} from './prepared-models';
import {prepareAttachedLines} from './prepared-attached-lines';
import {prepareAttachedSurfaces, writeAttachedSurfaces, disposeAttachedSurfaces} from './prepared-attached-surfaces';

const raw = {model_id:'surface', segments:[{name:'part', parent:null, primary_axis:'z', rest_orientation:[1,0,0,0], length_proportion:.1,is_fully_specified:true}],
    landmarks:[], connections:[], presentation:{excluded_bones:[], excluded_origin_edges:[], attached_lines:[{
        segment:'part', authored_length:.1, positions:[.1,0,0,0,.1,0], material:{color:'#b7bac2',opacity:.75},
        surfaces:[{positions:[.1,0,0,0,.1,0,0,0,.1], indices:[0,1,2], material:{color:'#a0b0e3',opacity:.21}, double_sided:false}],
    }]}};
test('surfaces share line pose math, reuse local buffers, hide invalid poses and dispose all resources', () => {
    const model=ModelDefinitionSchema.parse(raw), group=new Group();
    const frame:ResolvedModelFrame={modelId:'surface',instanceId:0,fittedScaleMm:1000,
        segmentOrigins:{names:['part'],data:Float32Array.from([10,20,30])},
        rotations:{boneNames:['part'],worldQuaternions:Float32Array.from([Math.SQRT1_2,0,0,Math.SQRT1_2]),localQuaternions:new Float32Array()},
        segmentLengths:{names:['part'],data:Float32Array.from([100]),fittedScaleMm:1000},
        mappedKeypoints:null,landmarks:null,derived:{centerOfMass:null,xcom:null}};
    const attached=prepareAttachedLines(prepareModels([frame],new Map([['surface',model]])),0);
    const batches=prepareAttachedSurfaces(attached,group), mesh=batches[0].meshes[0];
    const geometry=mesh.geometry, local=geometry.attributes.position.array, scratch=new Float64Array(9);
    for(let i=0;i<1000;i++)writeAttachedSurfaces(batches[0],frame,scratch);
    assert.equal(mesh.geometry,geometry);assert.equal(geometry.attributes.position.array,local);
    const p=new Vector3(.1,0,0).applyMatrix4(mesh.matrix);
    assert.ok(p.distanceTo(new Vector3(10,120,30))<1e-4);
    assert.equal(mesh.material.opacity,.21);assert.equal(mesh.material.depthWrite,false);
    assert.equal(attached[0].opacity,.75);
    frame.rotations=null;writeAttachedSurfaces(batches[0],frame,scratch);assert.equal(mesh.visible,false);
    let disposed=0;geometry.addEventListener('dispose',()=>disposed++);mesh.material.addEventListener('dispose',()=>disposed++);
    disposeAttachedSurfaces(batches);assert.equal(disposed,2);assert.equal(group.children.length,0);
});
test('malformed surface indices, opacity, and coordinates are rejected by the self-describing model schema',()=>{
    const changes:((s:typeof raw.presentation.attached_lines[number]['surfaces'][number])=>void)[] = [s=>{s.indices=[3,1,2];},s=>{s.material.opacity=1.1;},s=>{s.positions[0]=NaN;}];
    for(const change of changes){
        const invalid=structuredClone(raw);change(invalid.presentation.attached_lines[0].surfaces[0]);
        assert.equal(ModelDefinitionSchema.safeParse(invalid).success,false);
    }
});
