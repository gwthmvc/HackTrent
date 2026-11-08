const CHAT_API_URL = import.meta.env.VITE_CHAT_API_URL ?? '/api/chat';
const CHAT_TIMEOUT_MS = 60_000;

export type ChatMessage = {
    role: 'user' | 'model';
    parts: [{ text: string }];
};

export async function sendChatMessage(
    message: string,
    chatHistory: ChatMessage[],
): Promise<string> {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);

    try {
        const response = await fetch(CHAT_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, chatHistory }),
            signal: controller.signal,
        });

        const responseBody: unknown = await response.json().catch(() => undefined);
        if (!response.ok) {
            const errorMessage = typeof responseBody === 'object'
                && responseBody !== null
                && 'error' in responseBody
                && typeof responseBody.error === 'object'
                && responseBody.error !== null
                && 'message' in responseBody.error
                && typeof responseBody.error.message === 'string'
                ? responseBody.error.message
                : typeof responseBody === 'object'
                    && responseBody !== null
                    && 'error' in responseBody
                    && typeof responseBody.error === 'string'
                    ? responseBody.error
                : `Chat request failed with status ${response.status}.`;
            throw new Error(errorMessage);
        }

        if (
            typeof responseBody !== 'object'
            || responseBody === null
            || !('reply' in responseBody)
            || typeof responseBody.reply !== 'string'
        ) {
            throw new Error('The chat service returned an invalid response.');
        }

        return responseBody.reply;
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('The chat service did not respond within 60 seconds. Please try again.', {
                cause: error,
            });
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId); 
    }
}
