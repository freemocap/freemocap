import {transform} from 'esbuild';
import {readFileSync,writeFileSync,mkdirSync,readdirSync} from 'node:fs';
mkdirSync('.test-artifacts',{recursive:true});
for(const name of readdirSync('tests').filter(name=>name.endsWith('.test.ts'))){
 const {code}=await transform(readFileSync('tests/'+name,'utf8'),{loader:'ts',format:'esm',target:'es2022'});
 writeFileSync('.test-artifacts/'+name.replace(/\.ts$/,'.mjs'),code);
}
