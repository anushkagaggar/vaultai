import Link from 'next/link';
import type { Plan, BudgetPlan, InvestPlan, GoalPlan, SimulatePlan } from '../../lib/types/plans';
import { formatIndianCurrency, getRelativeTime } from '../../lib/planUtils';

const TYPE_META: Record<string, { label: string; color: string; route: string }> = {
  budget:   { label: 'Budget Plan',     color: '#3B82F6', route: '/plans/budget' },
  invest:   { label: 'Investment Plan', color: '#8B5CF6', route: '/plans/invest' },
  goal:     { label: 'Goal Plan',       color: '#10B981', route: '/plans/goal' },
  simulate: { label: 'Simulation',      color: '#F59E0B', route: '/simulate' },
};

function getSummary(plan: Plan): string {
  switch (plan.planType) {
    case 'budget': {
      const p = plan as BudgetPlan;
      return `Save ${formatIndianCurrency(p.monthlySavings)}/mo · ${Math.round(p.minSavingsRate * 100)}% savings rate`;
    }
    case 'invest': {
      const p = plan as InvestPlan;
      return `${p.riskProfile} risk · ${formatIndianCurrency(p.monthlyAmount)}/mo`;
    }
    case 'goal': {
      const p = plan as GoalPlan;
      return `${p.goalType.replace(/_/g, ' ')} · ${formatIndianCurrency(p.targetAmount)} in ${p.horizonMonths}mo`;
    }
    case 'simulate': {
      const p = plan as SimulatePlan;
      return `${formatIndianCurrency(p.monthlySavings)}/mo · ${p.horizonMonths}mo horizon`;
    }
  }
}

export default function PlanCard({ plan }: { plan: Plan }) {
  const meta = TYPE_META[plan.planType];
  const confidence = Math.round(plan.confidence.overall * 100);

  return (
    <div style={{
      background: '#1A1D27',
      border: '1px solid #2E3248',
      borderRadius: 12,
      padding: 20,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{
            fontSize: 11, padding: '3px 10px', borderRadius: 99,
            background: `${meta.color}18`, color: meta.color,
            border: `1px solid ${meta.color}30`, fontWeight: 600,
          }}>
            {meta.label}
          </span>
          {plan.degraded ? (
            <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 99, background: 'rgba(245,158,11,0.12)', color: '#F59E0B', fontWeight: 600 }}>
              Degraded
            </span>
          ) : (
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22C55E', display: 'inline-block' }} />
          )}
        </div>
        <span style={{
          fontSize: 13, fontWeight: 700, fontFamily: 'monospace',
          color: confidence >= 70 ? '#22C55E' : confidence >= 40 ? '#F59E0B' : '#EF4444',
        }}>
          {confidence}%
        </span>
      </div>

      <p style={{ fontSize: 13, color: '#94A3B8', margin: 0 }}>{getSummary(plan)}</p>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: '#475569', fontFamily: 'monospace' }}>
          {getRelativeTime(plan.createdAt)}
        </span>
        <Link
          href={`${meta.route}?id=${plan.id}`}
          style={{ fontSize: 12, color: '#6366F1', textDecoration: 'none', fontWeight: 500 }}
        >
          View Plan →
        </Link>
      </div>
    </div>
  );
}