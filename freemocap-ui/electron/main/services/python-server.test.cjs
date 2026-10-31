// Run from freemocap-ui: node --test electron/main/services/python-server.test.cjs
// Runs the real lifecycle service with a fake child process; no applications launch.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {transformSync} = require('esbuild');

const code = transformSync(readFileSync(path.join(__dirname, 'python-server.ts'), 'utf8'),
    {loader: 'ts', platform: 'node', format: 'cjs'}).code;

test('graceful child exit clears ownership and cannot kill a stale PID later', async () => {
    const children = [];
    const killed = [];
    const module = {exports: {}};
    const stubs = {
        child_process: {exec() {
            const child = Object.assign(new EventEmitter(), {
                pid: 1000 + children.length, killed: false, stdout: new EventEmitter(),
            });
            children.push(child);
            setImmediate(() => child.stdout.emit('data', 'FREEMOCAP_PORT=54329\n'));
            return child;
        }},
        'node:fs': {existsSync: () => true, statSync: () => ({isFile: () => true}),
            accessSync() {}, constants: {F_OK: 0, R_OK: 4, X_OK: 1}},
        './logger': {LifecycleLogger: {logPythonProcess() {}}},
        '../app-paths': {PYTHON_EXECUTABLE_CANDIDATES: []},
        '../base-folder': {getBaseDataFolder: () => 'test-data', FREEMOCAP_BASE_FOLDER_ENV_VAR: 'FREEMOCAP_BASE_FOLDER'},
        'tree-kill': (pid, callback) => {killed.push(pid); callback();},
    };
    vm.runInNewContext(code, {module, exports: module.exports, process, console,
        setTimeout, clearTimeout, require: name => stubs[name] ?? require(name)});
    const {PythonServer} = module.exports;
    assert.equal(await PythonServer.start('test-server.exe'), 54329);
    assert.equal(PythonServer.isRunning(), true);
    children[0].emit('exit', 0);
    assert.equal(PythonServer.isRunning(), false);
    assert.equal(PythonServer.getProcessInfo(), null);
    assert.equal(PythonServer.getCurrentExecutablePath(), null);
    await PythonServer.shutdown();
    assert.deepEqual(killed, []);
    await PythonServer.start('test-server.exe');
    // A delayed event from an earlier process must not clear its replacement.
    children[0].emit('error', new Error('late old-process event'));
    assert.equal(PythonServer.getProcessInfo().pid, children[1].pid);
    assert.equal(PythonServer.getCurrentExecutablePath(), 'test-server.exe');
    children[1].emit('exit', 0);
});
