const DEPARTURE_PATTERNS = [
    /\b(?:start(?:ing)?|depart(?:ing)?|leav(?:e|ing)|com(?:e|ing)|travell?ing)\s+(?:my\s+(?:trip|day|outing)\s+)?(?:from|at)\s+([^.!?\n]{3,120})/i,
    /\bpick\s+me\s+up\s+(?:from|at)\s+([^.!?\n]{3,120})/i,
    /\bmy\s+(?:starting|departure|pickup)\s+(?:point|location)\s*(?:is|will be|:)\s*([^.!?\n]{3,120})/i,
];

const TRAILING_DETAIL = /\s+(?:(?:and\s+)?then|and\s+(?:i|we|my|our)\b|to\s+(?:visit|see|go|attend|explore|spend)|this\s+(?:morning|afternoon|evening|weekend|week)|on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|at\s+\d|with\s+(?:a|my|our)|using\s+|by\s+(?:bus|train|car|transit)|for\s+(?:a|the|\d)|before\s+|after\s+|because\s+|so\s+)/i;

export function extractPromptStartingLocation(message: string): string | undefined {
    for (const pattern of DEPARTURE_PATTERNS) {
        const match = message.match(pattern);
        if (!match?.[1]) continue;

        const candidate = match[1]
            .split(TRAILING_DETAIL, 1)[0]
            .replace(/^[\s'"“”]+|[\s,'"“”]+$/g, '')
            .trim();

        if (candidate.length >= 3) return candidate;
    }

    return undefined;
}
