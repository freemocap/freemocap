/** Report a rejected stream message once per distinct error, not once per frame. */
export function subscribeToStreamErrors(
    transport: {subscribeToProtocolErrors: (callback: (error: unknown) => void) => () => void},
    report: (message: string) => void,
): () => void {
    let lastMessage: string | null = null;
    return transport.subscribeToProtocolErrors(error => {
        const detail = error instanceof Error ? error.message
            : typeof error === 'string' ? error : 'The server message did not match the expected format.';
        const message = `A live stream message could not be read. Some frames may be missing. ${detail}`;
        if (message === lastMessage) return;
        lastMessage = message;
        report(message);
    });
}
