// Pure formatting helpers — no mock data, safe to import anywhere

export function formatIndianCurrency(amount: number): string {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';
  if (abs >= 10_000_000) return `${sign}₹${(abs / 10_000_000).toFixed(2)}Cr`;
  if (abs >= 100_000)    return `${sign}₹${(abs / 100_000).toFixed(2)}L`;
  if (abs >= 1_000)      return `${sign}₹${(abs / 1_000).toFixed(1)}K`;
  return `${sign}₹${abs.toFixed(0)}`;
}

export function getRelativeTime(dateString: string): string {
  const diffMs   = Date.now() - new Date(dateString).getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHrs  = Math.floor(diffMs / 3_600_000);
  const diffDays = Math.floor(diffMs / 86_400_000);
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHrs  < 24) return `${diffHrs}h ago`;
  if (diffDays <  7) return `${diffDays}d ago`;
  return new Date(dateString).toLocaleDateString();
}