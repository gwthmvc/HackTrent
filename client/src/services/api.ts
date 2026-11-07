const API_BASE_URL = 'http://155.138.130.206/api';
const API_TIMEOUT_MS = 15_000;

type ApiErrorResponse = {
    message?: string;
    error?: string;
    detail?: string;
};

export async function post<TResponse>(
    path: string,
    body: Record<string, unknown>,
): Promise<TResponse> {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    let response: Response;
    try {
        response = await fetch(`${API_BASE_URL}${path}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
            signal: controller.signal,
        });
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('The server took too long to respond. Please try again.', {
                cause: error,
            });
        }
        throw new Error('Unable to connect to the server. Please try again.', {
            cause: error,
        });
    } finally {
        window.clearTimeout(timeoutId);
    }

    const contentType = response.headers.get('content-type');
    const responseBody: unknown = contentType?.includes('application/json')
        ? await response.json()
        : await response.text();

    if (!response.ok) {
        const apiError = typeof responseBody === 'object' && responseBody !== null
            ? responseBody as ApiErrorResponse
            : undefined;
        const message = apiError?.message ?? apiError?.error ?? apiError?.detail
            ?? (typeof responseBody === 'string' ? responseBody : undefined)
            ?? `Request failed with status ${response.status}`;

        throw new Error(message);
    }

    return responseBody as TResponse;
}
