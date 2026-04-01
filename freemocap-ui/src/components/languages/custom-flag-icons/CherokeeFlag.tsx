import React from "react";

/**
 * Simplified Cherokee Nation flag icon.
 *
 * Renders a gold seven-pointed star (representing the seven Cherokee clans)
 * centered on an orange field, matching the proportions and style used by
 * the country-flag-icons library (3:2 aspect ratio, 20×14px default).
 */
export const CherokeeFlag: React.FC<React.SVGProps<SVGSVGElement>> = (props) => {
  // Seven-pointed star vertices, computed for a unit circle centered at (10, 7)
  // with outer radius 5.5 and inner radius 2.5, starting from the top point.
  const outerRadius = 5.5;
  const innerRadius = 2.5;
  const cx = 10;
  const cy = 7;
  const points = 7;
  const angleStep = Math.PI / points;
  const startAngle = -Math.PI / 2; // top

  const starPoints: string[] = [];
  for (let i = 0; i < points * 2; i++) {
    const radius = i % 2 === 0 ? outerRadius : innerRadius;
    const angle = startAngle + i * angleStep;
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    starPoints.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  }

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 14"
      width={20}
      height={14}
      style={{ borderRadius: 2, flexShrink: 0 }}
      {...props}
    >
      <rect width="20" height="14" fill="#CF6924" />
      <polygon points={starPoints.join(" ")} fill="#F2C75C" />
    </svg>
  );
};
