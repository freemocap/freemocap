/** Compare validated message contents without allocating serialized copies. */
export function snapshotEqual(left: unknown, right: unknown): boolean {
    if (Object.is(left, right)) return true;
    if (left === null || right === null || typeof left !== 'object' || typeof right !== 'object') return false;
    if (Array.isArray(left) || Array.isArray(right)) {
        return Array.isArray(left) && Array.isArray(right) && left.length === right.length
            && left.every((value, index) => snapshotEqual(value, right[index]));
    }
    const a = left as Record<string, unknown>;
    const b = right as Record<string, unknown>;
    const keys = Object.keys(a);
    return keys.length === Object.keys(b).length
        && keys.every(key => Object.hasOwn(b, key) && snapshotEqual(a[key], b[key]));
}
