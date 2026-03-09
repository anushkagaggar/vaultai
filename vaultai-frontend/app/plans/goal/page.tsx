'use client';
import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Calendar, AlertTriangle, Target } from 'lucide-react';
import AuthenticatedLayout from '../../components/Authenticatedlayout';
import PlanConfidence from '../../components/PlanConfidence';
import GraphExecutionTrace from '../../components/GraphExecutionTrace';
import ProjectionChart from '../../components/ProjectionChart';
import GoalProgress from '../../components/GoalProgress';
import AssumptionsBlock from '../../components/AssumptionsBlock';
import { formatIndianCurrency, getRelativeTime } from '../../../lib/planUtils';
import { getPlan } from '../../../lib/backend';
import type { GoalPlan, DebtPayoffRow } from '../../../lib/types/plans';

const FEASIBILITY_COLOR: Record<string, string> = {
  FEASIBLE:   '#10B981',
  STRETCH:    '#F59E0B',
  INFEASIBLE: '#EF4444',
};

export default function GoalPlanPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const planId = searchParams.get('id');

  const [plan, setPlan] = useState<GoalPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!planId) { setError(true); setLoading(false); return; }
    getPlan(planId)
      .then((data) => setPlan(data as GoalPlan))
      .catch((e: Error) => {
        if (e.message === 'unauthorized') router.push('/auth');
        else setError(true);
      })
      .finally(() => setLoading(false));
  }, [planId, router]);

  if (loading) return (
    <AuthenticatedLayout title="Goal Plan">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
        <p style={{ fontSize: 13, color: '#475569' }}>Loading plan...</p>
      </div>
    </AuthenticatedLayout>
  );

  if (error || !plan) return (
    <AuthenticatedLayout title="Goal Plan">
      <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12, padding: 32, textAlign: 'center' }}>
        <p style={{ fontSize: 14, color: '#EF4444', margin: 0 }}>Plan not found or failed to load.</p>
      </div>
    </AuthenticatedLayout>
  );

  const fColor = FEASIBILITY_COLOR[plan.feasibilityLabel];

  // Fix: explicitly type l as string to resolve implicit any
  const goalTitle = plan.goalType
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l: string) => l.toUpperCase());

  return (
    <AuthenticatedLayout title="Goal Plan">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Header */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: 'rgba(16,185,129,0.15)', color: '#10B981' }}>
                Goal Plan
              </span>
              <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: `${fColor}20`, color: fColor }}>
                {plan.feasibilityLabel}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94A3B8' }}>
              <Calendar size={12} /> {getRelativeTime(plan.createdAt)}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'start' }}>
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', margin: '0 0 6px' }}>{goalTitle}</h2>
              <p style={{ fontSize: 13, color: '#CBD5E1', margin: 0 }}>
                Target: {formatIndianCurrency(plan.targetAmount)} in {plan.horizonMonths} months
              </p>
            </div>
            <PlanConfidence confidence={plan.confidence} />
          </div>
        </div>

        {/* Summary cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14 }}>
          {[
            { label: 'Target Amount', value: formatIndianCurrency(plan.targetAmount), color: '#6366F1',  Icon: Target },
            { label: 'Time Horizon',  value: `${plan.horizonMonths} months`,          color: '#10B981',  Icon: Calendar },
            { label: 'Coverage',      value: `${Math.round(plan.coverageRatio * 100)}%`, color: fColor, Icon: Target },
          ].map(({ label, value, color, Icon }) => (
            <div key={label} style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <Icon size={14} color={color} />
                <p style={{ fontSize: 11, color: '#94A3B8', margin: 0 }}>{label}</p>
              </div>
              <p style={{ fontSize: 22, fontWeight: 800, color, margin: 0, fontFamily: 'monospace' }}>{value}</p>
            </div>
          ))}
        </div>

        <GoalProgress
          targetAmount={plan.targetAmount}
          projectedBalance={plan.projectedBalance}
          coverageRatio={plan.coverageRatio}
          feasibilityLabel={plan.feasibilityLabel}
          gapAmount={plan.gapAmount}
          monthsToGoal={plan.monthsToGoal}
        />

        <ProjectionChart data={plan.projection} targetAmount={plan.targetAmount} label="Savings Trajectory" />

        {/* Adjusted timeline warning */}
        {plan.adjustedTimeline && (
          <div style={{ padding: 16, borderRadius: 10, background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <AlertTriangle size={18} color="#F59E0B" style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <p style={{ fontSize: 13, fontWeight: 600, color: '#F59E0B', margin: '0 0 4px' }}>
                Goal not reached — adjusted timeline shown
              </p>
              <p style={{ fontSize: 12, color: '#CBD5E1', margin: '0 0 2px' }}>
                Original: {plan.adjustedTimeline.originalHorizon} months → Adjusted: {plan.adjustedTimeline.adjustedHorizon} months
              </p>
              <p style={{ fontSize: 12, color: '#94A3B8', margin: 0 }}>{plan.adjustedTimeline.reason}</p>
            </div>
          </div>
        )}

        {/* Debt payoff table — Fix: explicitly type row as DebtPayoffRow */}
        {plan.debtPayoffSchedule && (
          <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, overflow: 'hidden' }}>
            <div style={{ padding: '12px 20px', background: '#0F1117', borderBottom: '1px solid #2E3248' }}>
              <p style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>
                Debt Payoff Schedule
              </p>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #2E3248' }}>
                    {['Month', 'Opening', 'Interest', 'Principal', 'Closing'].map((h) => (
                      <th key={h} style={{ padding: '10px 16px', textAlign: h === 'Month' ? 'left' : 'right', fontSize: 11, fontWeight: 600, color: '#475569', textTransform: 'uppercase' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {plan.debtPayoffSchedule.map((row: DebtPayoffRow) => (
                    <tr key={row.month} style={{ borderBottom: '1px solid #2E3248' }}>
                      <td style={{ padding: '12px 16px', fontSize: 13, color: '#F1F5F9' }}>{row.month}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: 13, color: '#94A3B8',  fontFamily: 'monospace' }}>{formatIndianCurrency(row.openingBalance)}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: 13, color: '#EF4444',  fontFamily: 'monospace' }}>{formatIndianCurrency(row.interest)}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: 13, color: '#10B981',  fontFamily: 'monospace' }}>{formatIndianCurrency(row.principal)}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: 13, color: '#F1F5F9',  fontFamily: 'monospace', fontWeight: 600 }}>{formatIndianCurrency(row.closingBalance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Multi-goal view */}
        {plan.multiGoal && plan.multiGoal.totalGoals > 1 && (
          <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, overflow: 'hidden' }}>
            <div style={{ padding: '12px 20px', background: '#0F1117', borderBottom: '1px solid #2E3248' }}>
              <p style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>
                Multi-Goal Allocation ({plan.multiGoal.totalGoals} goals)
              </p>
            </div>
            <div>
              {plan.multiGoal.goals.map((goal, idx) => {
                const gc = FEASIBILITY_COLOR[goal.feasibility];
                return (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #2E3248' }}>
                    <div>
                      <p style={{ fontSize: 13, fontWeight: 500, color: '#F1F5F9', margin: '0 0 2px' }}>{goal.name}</p>
                      <p style={{ fontSize: 11, color: '#94A3B8', margin: 0 }}>Target: {formatIndianCurrency(goal.targetAmount)}</p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <p style={{ fontSize: 13, fontWeight: 600, color: '#6366F1', margin: 0, fontFamily: 'monospace' }}>
                        {formatIndianCurrency(goal.monthlyAllocated)}/mo
                      </p>
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 99, background: `${gc}18`, color: gc, fontWeight: 600 }}>
                        {goal.feasibility}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* AI Narration */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 99, background: 'rgba(99,102,241,0.15)', color: '#A5B4FC', fontWeight: 600 }}>
            AI Narration
          </span>
          <p style={{ fontSize: 14, color: '#CBD5E1', margin: '12px 0 0', lineHeight: 1.7 }}>{plan.explanation}</p>
        </div>

        <GraphExecutionTrace nodes={plan.graphTrace} validationStatus={plan.validationStatus} />
        <AssumptionsBlock assumptions={plan.assumptions} />
      </div>
    </AuthenticatedLayout>
  );
}