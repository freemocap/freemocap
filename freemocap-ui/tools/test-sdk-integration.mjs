import {build} from 'esbuild';
import {readdirSync,mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const output='../.test-artifacts/sdk-integration';
mkdirSync(output,{recursive:true});
const specialized=new Set(['camera-server-settings.test.ts','camera-control-requests.test.ts','operation-progress.test.tsx']);
function tests(directory){return readdirSync(directory,{withFileTypes:true}).flatMap(entry=>
 entry.isDirectory()?tests(`${directory}/${entry.name}`):/\.test\.tsx?$/.test(entry.name)&&!specialized.has(entry.name)?[`${directory}/${entry.name}`]:[]);}
const inputs=tests('src');
const outputs=inputs.map(file=>`${output}/${file.split('/').at(-1).replace(/\.tsx?$/,'.cjs')}`);
await Promise.all(inputs.map((file,index)=>build({entryPoints:[file],outfile:outputs[index],bundle:true,
 platform:'node',format:'cjs',external:['cbor-extract'],loader:{'.yaml':'text'}})));
const commands=[['--test',...outputs],
 ['tools/test-camera-settings.mjs',`${output}/camera-server-settings.test.cjs`],
 ['tools/test-camera-settings.mjs',`${output}/camera-control-requests.test.cjs`,'src/store/slices/cameras/camera-control-requests.test.ts'],
 ['src/components/pipeline-progress/run-operation-progress-tests.mjs']];
for(const command of commands){const result=spawnSync(process.execPath,command,{stdio:'inherit'});if(result.status!==0)process.exit(result.status??1);}
