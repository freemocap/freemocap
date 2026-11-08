#!/usr/bin/env node
// Installs and builds the local @freemocap/client package before the UI uses it.
//
// The UI depends on file:../packages/freemocap-client. npm only links a folder
// outside this project; it does not install that folder's dependencies or build
// it [@npmInstallFolderV10]. The package exports dist/ output, so Vite and tsc
// cannot resolve it until it is built. This repeats the installer workflow's
// "Build local JavaScript client" step and skips each half when it is current.
// package.json runs it from postinstall and the dev, build and test pre-scripts
// [@npmScriptsV10].
import {spawnSync} from 'node:child_process'
import {existsSync, readdirSync, readFileSync, statSync} from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'

const uiRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const clientRoot = path.resolve(uiRoot, '..', 'packages', 'freemocap-client')
const tag = '[freemocap-client]'

const mtime = (file) => statSync(file).mtimeMs

function newestFileMtime(dir) {
    let newest = 0
    for (const entry of readdirSync(dir, {withFileTypes: true})) {
        const full = path.join(dir, entry.name)
        newest = Math.max(newest, entry.isDirectory() ? newestFileMtime(full) : mtime(full))
    }
    return newest
}

// Every concrete file the package manifest promises to consumers.
function promisedOutputs(manifest) {
    const targets = new Set([manifest.main, manifest.types].filter(Boolean))
    const visit = (value) => {
        if (typeof value === 'string') targets.add(value)
        else if (value && typeof value === 'object') Object.values(value).forEach(visit)
    }
    visit(manifest.exports)
    return [...targets].filter((target) => !target.includes('*')).map((target) => path.join(clientRoot, target))
}

function runNpm(args) {
    const command = `npm ${args.join(' ')}`
    console.log(`${tag} ${command}`)
    // A constant command through the shell also resolves npm.cmd on Windows.
    const result = spawnSync(command, {cwd: clientRoot, stdio: 'inherit', shell: true})
    if (result.status !== 0) {
        console.error(`${tag} "${command}" failed in ${clientRoot}`)
        process.exit(result.status ?? 1)
    }
}

const manifestFile = path.join(clientRoot, 'package.json')
if (!existsSync(manifestFile)) {
    console.error(`${tag} expected the client package at ${clientRoot}`)
    process.exit(1)
}

// npm writes node_modules/.package-lock.json when an install completes.
const installedLock = path.join(clientRoot, 'node_modules', '.package-lock.json')
const lockFile = path.join(clientRoot, 'package-lock.json')
if (!existsSync(installedLock) || mtime(installedLock) < Math.max(mtime(lockFile), mtime(manifestFile))) {
    // --include=dev keeps the client's TypeScript even if this install omits dev
    // dependencies [@npmIncludeConfigV10].
    runNpm(['ci', '--ignore-scripts', '--include=dev', '--no-audit', '--no-fund'])
}

const outputs = promisedOutputs(JSON.parse(readFileSync(manifestFile, 'utf8')))
const newestInput = Math.max(
    newestFileMtime(path.join(clientRoot, 'src')),
    mtime(manifestFile),
    mtime(path.join(clientRoot, 'tsconfig.json')),
    mtime(installedLock),
)
const current = outputs.length > 0 && outputs.every((file) => existsSync(file) && mtime(file) >= newestInput)
if (current) {
    console.log(`${tag} build is up to date`)
} else {
    runNpm(['run', 'build'])
}
