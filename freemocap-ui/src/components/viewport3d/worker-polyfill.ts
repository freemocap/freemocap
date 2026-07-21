// Vite's Fast Refresh transform injects `window`, `$RefreshReg$`, and `$RefreshSig$`
// into every React file. None of these exist in Web Worker scope. Stub them out so
// the preamble doesn't throw. Must be imported before any React modules in the worker.
(globalThis as any).window ??= globalThis;
(globalThis as any).$RefreshReg$ ??= () => {};
// $RefreshSig$ must return a passthrough function (wraps component for HMR tracking)
(globalThis as any).$RefreshSig$ ??= () => (type: unknown) => type;
