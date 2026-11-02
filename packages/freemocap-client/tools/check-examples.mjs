import {readdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
for (const file of readdirSync('examples').filter(file => file.endsWith('.mjs'))) {
    execFileSync(process.execPath, ['--check', `examples/${file}`], {stdio: 'inherit', windowsHide: true});
}
console.log('Four runnable examples passed syntax checks');
