import assert from 'node:assert/strict';
import {readFileSync, writeFileSync} from 'node:fs';
import {operationDefinitions} from '../dist/generated/operations.js';
const contract = JSON.parse(readFileSync('contracts/operations.json', 'utf8'));
const schema = JSON.parse(readFileSync('contracts/openapi.json', 'utf8'));
assert.equal(contract.public_http.length, Object.values(schema.paths).flatMap(methods =>
    Object.values(methods).filter(operation => operation.operationId)).length);
assert.deepEqual(Object.keys(operationDefinitions).sort(), contract.public_http.map(item => item.operation_id).sort());
const lines = ['# HTTP operation coverage', '',
    'Generated from the reviewed ledger; run `npm run coverage` after building.', '',
    'Every row has a typed binding and an HTTP method/path conformance case in `http-conformance.mjs`.',
    'This is coverage, not proof that every server-side effect was executed. Shared tests cover serialization,',
    'errors, aborts, cancellation and asset ownership; compatibility records list actual integration workflows.', '',
    '| Method | Path | Operation ID | Owner |', '| --- | --- | --- | --- |'];
for (const item of contract.public_http) {
    assert.equal(operationDefinitions[item.operation_id].method, item.method);
    assert.equal(operationDefinitions[item.operation_id].path, item.path);
    lines.push(`| ${item.method} | \`${item.path}\` | \`${item.operation_id}\` | ${item.owner} |`);
}
const text = lines.join('\n') + '\n';
// Git may check the committed LF file out with CRLF endings (core.autocrlf on Windows).
if (process.argv.includes('--check')) assert.equal(readFileSync('contracts/coverage.md', 'utf8').replace(/\r\n/g, '\n'), text);
else writeFileSync('contracts/coverage.md', text);
console.log(`${contract.public_http.length} operation bindings and coverage entries verified`);
