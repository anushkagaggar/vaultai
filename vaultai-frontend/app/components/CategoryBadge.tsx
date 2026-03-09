export type Category =
  | "Food"
  | "Transport"
  | "Shopping"
  | "Utilities"
  | "Health"
  | "Entertainment"
  | "Other";

const CATEGORY_COLORS: Record<Category, { bg: string; color: string }> = {
  Food:          { bg: "rgba(249,115,22,0.12)",  color: "#F97316" },
  Transport:     { bg: "rgba(59,130,246,0.12)",  color: "#3B82F6" },
  Shopping:      { bg: "rgba(236,72,153,0.12)",  color: "#EC4899" },
  Utilities:     { bg: "rgba(139,92,246,0.12)",  color: "#8B5CF6" },
  Health:        { bg: "rgba(16,185,129,0.12)",  color: "#10B981" },
  Entertainment: { bg: "rgba(245,158,11,0.12)",  color: "#F59E0B" },
  Other:         { bg: "rgba(107,114,128,0.12)", color: "#6B7280" },
};

export function CategoryBadge({ category }: { category: string }) {
  const c = CATEGORY_COLORS[category as Category] ?? CATEGORY_COLORS.Other;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 10px",
        borderRadius: 99,
        fontSize: 11,
        fontWeight: 600,
        background: c.bg,
        color: c.color,
        letterSpacing: "0.03em",
      }}
    >
      {category}
    </span>
  );
}