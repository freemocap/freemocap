/** Source guard: declarations anywhere in src, exact-case icon paths, and new hex literals. */
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const root = path.resolve(import.meta.dirname, '..');
const base = process.env.UI_BASELINE_COMMIT || '8c209ec2';
const files = fs.readdirSync(path.join(root, 'src'), {recursive:true}).filter(f => /\.(css|tsx?|jsx?)$/.test(f)).sort();
const sources = files.map(f => [f, fs.readFileSync(path.join(root,'src',f),'utf8').replace(/\/\*[\s\S]*?\*\//g,'')]);
const declarations = new Set();
for (const [,text] of sources) {
  for (const m of text.matchAll(/(--[\w-]+)\s*['"]?\s*:/g)) declarations.add(m[1]);
  for (const m of text.matchAll(/setProperty\(\s*['"](--[\w-]+)['"]/g)) declarations.add(m[1]);
}
const errors = [];
for (const [file,text] of sources) {
  for (const m of text.matchAll(/var\(\s*(--[\w-]+)/g)) if (!declarations.has(m[1])) errors.push(`${file}: undefined ${m[1]}`);
  if (file === 'styles/color.css') continue;
  const count = value => {const result = {}; for (const m of value.matchAll(/#[\da-fA-F]{3,8}\b/g)) result[m[0].toLowerCase()] = (result[m[0].toLowerCase()] || 0)+1; return result;};
  let old = ''; try {old = execFileSync('git',['show',`${base}:freemocap-ui/src/${file}`],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','ignore']}).replace(/\/\*[\s\S]*?\*\//g,'');} catch {}
  const before=count(old);
  for (const [hex,n] of Object.entries(count(text))) if (n > (before[hex] || 0)) errors.push(`${file}: ${n-(before[hex]||0)} new ${hex} literal(s)`);
}
const icons = fs.readFileSync(path.join(root,'src/styles/icons.css'),'utf8').replace(/\/\*[\s\S]*?\*\//g,'');
for (const m of icons.matchAll(/url\(\s*['"]?([^)'"\s]+)['"]?\s*\)/g)) {
  if (/^(data:|https?:)/.test(m[1])) continue;
  const target = m[1].split(/[?#]/)[0];
  const absolute = target.startsWith('/') ? path.join(root,'public',target) : path.resolve(root,'src/styles',target);
  let current=path.parse(absolute).root;
  for(const part of absolute.slice(current.length).split(path.sep)) {
    if (!fs.existsSync(current) || !fs.readdirSync(current).includes(part)) {errors.push(`icons.css: missing or wrong filename case: ${target}`); break;}
    current=path.join(current,part);
  }
}
console.log(JSON.stringify({base,files:files.length,declarations:declarations.size,errors:[...new Set(errors)]},null,2));
process.exitCode=errors.length ? 1 : 0;
