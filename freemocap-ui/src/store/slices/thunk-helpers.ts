/**
 * Shared utilities for async thunks that call the backend HTTP API.
 */

function describeError(details: unknown): string {
    if (typeof details === 'string') return details;
    if (Array.isArray(details)) return details.map(describeError).filter(Boolean).join('\n');
    if (details !== null && typeof details === 'object') {
        const entry = details as Record<string, unknown>;
        if (typeof entry.msg === 'string') {
            const path = Array.isArray(entry.loc) ? entry.loc.join('.') : '';
            return path ? `${path}: ${entry.msg}` : entry.msg;
        }
        for (const key of ['detail', 'message', 'error']) {
            if (entry[key] != null) {
                const description = describeError(entry[key]);
                if (description) return description;
            }
        }
        return JSON.stringify(details);
    }
    return details == null ? '' : String(details);
}

/** Read once: a failed response.json() also consumes a plain-text response body. */
export async function getDetailedErrorMessage(response: Response): Promise<string> {
    const baseError = `HTTP ${response.status}${response.statusText ? `: ${response.statusText}` : ''}`;
    let body: string;
    try {
        body = await response.text();
    } catch {
        return baseError;
    }
    let details: unknown = body;
    try {
        details = JSON.parse(body);
    } catch {
        // A proxy or server failure can return plain text instead of JSON.
    }
    const description = describeError(details);
    return description ? `${baseError}\n${description}` : baseError;
}
