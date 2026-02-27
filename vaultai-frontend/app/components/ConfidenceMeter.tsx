export default function ConfidenceMeter({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  const radius = 36;
  const circ = Math.PI * radius;
  const fill = (value * circ).toFixed(1);
  const color = value >= 0.7 ? "#22C55E" : value >= 0.4 ? "#F59E0B" : "#EF4444";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width="100" height="58" viewBox="0 0 100 58">
        {/* Background arc */}
        <path
          d="M 9 52 A 40 40 0 0 1 91 52"
          fill="none"
          stroke="#2E3248"
          strokeWidth="7"
          strokeLinecap="round"
        />
        {/* Foreground arc */}
        <path
          d="M 9 52 A 40 40 0 0 1 91 52"
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${fill} ${circ}`}
          style={{ transition: "stroke-dasharray 0.8s ease" }}
        />
        {/* Percentage text */}
        <text
          x="50"
          y="50"
          textAnchor="middle"
          fill={color}
          fontSize="16"
          fontWeight="700"
          fontFamily="'JetBrains Mono', monospace"
        >
          {percent}%
        </text>
      </svg>
      <span
        style={{
          fontSize: 10,
          fontWeight: 500,
          color: "#475569",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
        }}
      >
        Confidence
      </span>
    </div>
  );
}