// Software-rendered deterministic fixture. Run from freemocap-ui after preparing
// ../.test-artifacts/skelly/reference-model.json; no app server/cameras are started.
import {build} from 'esbuild';
import {chromium} from '@playwright/test';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve('../.test-artifacts/skelly');
const reference = JSON.parse(await readFile(resolve(output, 'reference-model.json'), 'utf8'));
const entry = `
import {Scene, PerspectiveCamera, WebGLRenderer, AmbientLight, DirectionalLight, Color} from 'three';
import asset from './src/components/viewport3d/renderers/skelly/skelly.json';
import {createSkellyMesh, prepareSkellyRows, updateSkellyPose, skellyCompatible} from './src/components/viewport3d/renderers/skelly/skelly-binding';
const reference=${JSON.stringify(reference)};
if (!skellyCompatible(asset, reference.definition)) throw Error('Current server model projection is incompatible with the artwork');
const scene=new Scene(); scene.background=new Color('#121824');
const camera=new PerspectiveCamera(40,1,1,10000); camera.up.set(0,0,1); camera.position.set(0,3600,200); camera.lookAt(0,0,0);
scene.add(new AmbientLight(0xffffff,1.5)); const light=new DirectionalLight(0xffffff,2); light.position.set(1500,2000,2000); scene.add(light);
const mesh=createSkellyMesh(asset); scene.add(mesh);
const names=asset.parts.map(p=>p.name);
const frame={modelId:'fixture', instanceId:0, fittedScaleMm:1700,
segmentOrigins:{names,stride:3,data:Float32Array.from(names.flatMap(n=>reference.origins[n].map(x=>x*1700)))},
rotations:{boneNames:names,worldQuaternions:Float32Array.from(names.flatMap(n=>reference.rotations[n]))},
segmentLengths:{names,data:Float32Array.from(asset.parts.map(p=>p.authoredLength*1700)),fittedScaleMm:1700}};
updateSkellyPose(mesh,asset,prepareSkellyRows(asset,frame),frame);
const renderer=new WebGLRenderer({antialias:true,preserveDrawingBuffer:true}); renderer.setSize(800,800); document.body.appendChild(renderer.domElement);
const gl=renderer.getContext(), extension=gl.getExtension('WEBGL_debug_renderer_info');
const device=extension?gl.getParameter(extension.UNMASKED_RENDERER_WEBGL):'unknown';
if(!device.includes('SwiftShader')) throw Error('Expected CPU software renderer: '+device);
renderer.render(scene,camera);
window.skellyResult={device,calls:renderer.info.render.calls,triangles:renderer.info.render.triangles};
`;
const bundle = await build({stdin: {contents: entry, resolveDir: process.cwd(), loader: 'ts'}, bundle: true, write: false, format: 'iife'});
const browser = await chromium.launch({headless: true, executablePath: process.env.SKELLY_TEST_BROWSER ?? 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-sandbox']});
try {
    const page = await browser.newPage({viewport: {width: 800, height: 800}});
    const errors = []; page.on('pageerror', error => errors.push(String(error)));
    await page.setContent('<body style="margin:0"></body>');
    await page.addScriptTag({content: bundle.outputFiles[0].text});
    const result = await page.evaluate(() => window.skellyResult);
    assert.deepEqual(errors, []); assert.equal(result.triangles, 20432); assert.equal(result.calls, 3);
    await page.screenshot({path: resolve(output, 'skelly-rest.png')});
    await writeFile(resolve(output, 'web-result.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
} finally {await browser.close();}
