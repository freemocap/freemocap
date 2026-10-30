/** Exact content equality: no rounding, hashing, or tolerance-based motion suppression. */
export function equalBytes(left: Uint8Array, right: Uint8Array): boolean {
    if (left === right) return true;
    if (left.byteLength !== right.byteLength) return false;
    for (let index = 0; index < left.byteLength; index++) if (left[index] !== right[index]) return false;
    return true;
}
