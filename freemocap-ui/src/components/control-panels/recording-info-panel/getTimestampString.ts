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

    return `${partMap.year}-${partMap.month}-${partMap.day}_${
        partMap.hour
    }-${partMap.minute}-${partMap.second}_${partMap.timeZoneName.replace(
        ":",
        ""
    )}`;
};
