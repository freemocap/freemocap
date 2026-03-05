/**
 * Shared utilities for async thunks that call the backend HTTP API.
 */

/**
 * Extract a detailed error message from a failed HTTP response.
 * Attempts to parse JSON first, falls back to text, builds a
 * comprehensive error string including status code and body.
 */
export async function getDetailedErrorMessage(response: Response): Promise<string> {
    let errorDetails: unknown;

    try {
        errorDetails = await response.json();
        console.error('❌ Server returned validation/error details:', errorDetails);
    } catch {
        try {
            errorDetails = await response.text();
            console.error('❌ Server returned error text:', errorDetails);
        } catch {
            console.error('❌ Could not read error response body');
        }
    }

    const baseError = `HTTP ${response.status}: ${response.statusText}`;

    if (errorDetails) {
        const detailsStr = typeof errorDetails === 'string'
            ? errorDetails
            : JSON.stringify(errorDetails, null, 2);
        return `${baseError}\n\nValidation/Error Details:\n${detailsStr}`;
    }

    return baseError;
}
