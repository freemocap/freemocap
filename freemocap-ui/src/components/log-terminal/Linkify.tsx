import React from 'react';

// Splits text on http/https URLs. When split() is called with a capture group,
// matched segments land at odd indices, so i % 2 === 1 identifies URLs.
const URL_REGEX = /(https?:\/\/[^\s)"'>\]]+)/g;

export const Linkify = ({text}: {text: string}) => {
    const parts = text.split(URL_REGEX);
    if (parts.length === 1) return <>{text}</>;

    return (
        <>
            {parts.map((part, i) =>
                i % 2 === 1 ? (
                    <a
                        key={i}
                        href={part}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{color: "#58a6ff", textDecoration: "underline"}}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {part}
                    </a>
                ) : (
                    <span key={i}>{part}</span>
                )
            )}
        </>
    );
};
