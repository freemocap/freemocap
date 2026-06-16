import React from "react";

/**
 * Yiddish language flag icon.
 *
 * Renders two horizontal black stripes on a white field (evoking the
 * Ashkenazi tallit / prayer shawl) with a seven-branched menorah centered
 * between the stripes. Matches the 3:2 aspect ratio and sizing conventions
 * used by the country-flag-icons library (20×14px default).
 */
export const YiddishFlag: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 60 42"
    width={20}
    height={14}
    style={{ borderRadius: 2, flexShrink: 0 }}
    {...props}
  >
    {/* White background */}
    <rect width="60" height="42" fill="#fff" />

    {/* Top and bottom black stripes (tallit) */}
    <rect x="0" y="6" width="60" height="4" fill="#222" />
    <rect x="0" y="32" width="60" height="4" fill="#222" />

    {/* Seven-branched menorah — centered at (30, 22) */}
    <g fill="none" stroke="#222" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {/* Base */}
      <line x1="25" y1="30" x2="35" y2="30" />
      {/* Stem */}
      <line x1="30" y1="30" x2="30" y2="16" />

      {/* Center branch (tallest) — just the flame holder */}
      <line x1="30" y1="16" x2="30" y2="14" />

      {/* Inner branches (2) */}
      <path d="M30,22 C28,22 26,18 26,15" />
      <path d="M30,22 C32,22 34,18 34,15" />

      {/* Middle branches (2) */}
      <path d="M30,24 C26,24 23,18 22,15" />
      <path d="M30,24 C34,24 37,18 38,15" />

      {/* Outer branches (2) */}
      <path d="M30,26 C24,26 20,18 18,15" />
      <path d="M30,26 C36,26 40,18 42,15" />

      {/* Flames (small circles at the top of each branch) */}
      <circle cx="18" cy="14" r="1" fill="#222" stroke="none" />
      <circle cx="22" cy="14" r="1" fill="#222" stroke="none" />
      <circle cx="26" cy="14" r="1" fill="#222" stroke="none" />
      <circle cx="30" cy="13.5" r="1" fill="#222" stroke="none" />
      <circle cx="34" cy="14" r="1" fill="#222" stroke="none" />
      <circle cx="38" cy="14" r="1" fill="#222" stroke="none" />
      <circle cx="42" cy="14" r="1" fill="#222" stroke="none" />
    </g>
  </svg>
);
