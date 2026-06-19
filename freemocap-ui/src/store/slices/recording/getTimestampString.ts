/**
 * Generate a filesystem-safe recording timestamp like `2026-06-18_19-42-31_GMT-4`.
 *
 * This is the single source of truth for new-recording timestamps. It is used both
 * for the live "what will the next recording be called" preview and to mint a fresh
 * recording id at the moment a capture actually starts. Import this rather than
 * re-implementing the format.
 */
export const getTimestampString = (): string => {
    const now = new Date();

    const dateOptions: Intl.DateTimeFormatOptions = {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        timeZoneName: "shortOffset",
    };

    const formatter = new Intl.DateTimeFormat("en-US", dateOptions);
    const parts = formatter.formatToParts(now);

    const partMap: Record<string, string> = {};
    parts.forEach((part) => {
        partMap[part.type] = part.value;
    });

    return `${partMap.year}-${partMap.month}-${partMap.day}_${partMap.hour}-${partMap.minute}-${partMap.second}_${partMap.timeZoneName.replace(":", "")}`;
};
