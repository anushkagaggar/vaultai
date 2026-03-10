'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Plus } from 'lucide-react';
import AuthenticatedLayout from '../components/Authenticatedlayout';
import PlanCard from '../components/PlanCard';
import { getPlan } from '../../lib/backend';
import type { Plan, PlanType } from '../../lib/types/plans';

// ─── localStorage helpers ─────────────────────────────────────────────────────
// Plan IDs are saved here whenever a plan is created via Strategy/Chat page.
// Key: "vault_plan_ids" → JSON array of { id: string, planType: PlanType }

export interface StoredPlanRef {
  id: string;
  planType: PlanType;
}

export function savePlanRef(ref: StoredPlanRef) {
  try {
    const existing = loadPlanRefs();
    const deduped = existing.filter((r) => r.id !== ref.id);
    localStorage.setItem('vault_plan_ids', JSON.stringify([ref, ...deduped]));
  } catch {}
}

export function loadPlanRefs(): StoredPlanRef[] {
  try {
    return JSON.parse(localStorage.getItem('vault_plan_ids') ?? '[]');
  } catch {
    return [];
  }
}

// ─────────────────────────────────────────────────────────────────────────────

type FilterType = 'all' | PlanType;

const FILTERS: { value: FilterType; label: string }[] = [
  { value: 'all',      label: 'All' },
  { value: 'budget',   label: 'Budget' },
  { value: 'invest',   label: 'Invest' },
  { value: 'goal',     label: 'Goal' },
  { value: 'simulate', label: 'Simulate' },
];

const PLANS_PER_PAGE = 10;

export default function PlansPage() {
  const router = useRouter();
  const [allPlans, setAllPlans]     = useState<Plan[]>([]);
  const [loading, setLoading]       = useState(true);
  const [filter, setFilter]         = useState<FilterType>('all');
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    const refs = loadPlanRefs();
    if (refs.length === 0) { setLoading(false); return; }

    Promise.allSettled(refs.map((r) => getPlan(r.id)))
      .then((results) => {
        const plans: Plan[] = [];
        results.forEach((r, i) => {
          if (r.status === 'fulfilled') {
            plans.push(r.value);
          } else if ((r.reason as Error)?.message === 'unauthorized') {
            router.push('/auth');
          }
          // silently skip individual 404s (plan deleted on backend)
        });
        setAllPlans(plans);
      })
      .finally(() => setLoading(false));
  }, [router]);

  const filteredPlans: Plan[] =
    filter === 'all' ? allPlans : allPlans.filter((p) => p.planType === filter);

  const totalPages    = Math.ceil(filteredPlans.length / PLANS_PER_PAGE);
  const displayedPlans = filteredPlans.slice(
    (currentPage - 1) * PLANS_PER_PAGE,
    currentPage * PLANS_PER_PAGE,
  );

  return (
    <AuthenticatedLayout title="My Plans">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <p style={{ fontSize: 13, color: '#94A3B8', margin: 0 }}>View and manage your financial plans</p>
        <Link
          href="/strategy"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500, color: 'white', background: '#6366F1', textDecoration: 'none' }}
        >
          <Plus size={14} /> New Plan
        </Link>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24, overflowX: 'auto', paddingBottom: 4 }}>
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => { setFilter(f.value); setCurrentPage(1); }}
            style={{
              padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              cursor: 'pointer', whiteSpace: 'nowrap', background: 'none',
              color: filter === f.value ? '#F1F5F9' : '#94A3B8',
              border: `1px solid ${filter === f.value ? '#6366F1' : '#2E3248'}`,
              backgroundColor: filter === f.value ? '#22263A' : 'transparent',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <p style={{ fontSize: 13, color: '#475569' }}>Loading plans...</p>
        </div>
      )}

      {/* Empty */}
      {!loading && displayedPlans.length === 0 && (
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 48, textAlign: 'center' }}>
          <p style={{ fontSize: 14, color: '#94A3B8', marginBottom: 16 }}>
            No plans yet — start in Strategy Lab
          </p>
          <Link
            href="/strategy"
            style={{ padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500, color: 'white', background: '#6366F1', textDecoration: 'none' }}
          >
            Create First Plan
          </Link>
        </div>
      )}

      {/* Grid */}
      {!loading && displayedPlans.length > 0 && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
            {displayedPlans.map((plan) => (
              <PlanCard key={plan.id} plan={plan} />
            ))}
          </div>

          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8 }}>
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, background: '#1A1D27', border: '1px solid #2E3248', color: '#F1F5F9', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', opacity: currentPage === 1 ? 0.5 : 1 }}
              >
                Previous
              </button>
              <span style={{ padding: '8px 12px', fontSize: 13, color: '#94A3B8' }}>
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, background: '#1A1D27', border: '1px solid #2E3248', color: '#F1F5F9', cursor: currentPage === totalPages ? 'not-allowed' : 'pointer', opacity: currentPage === totalPages ? 0.5 : 1 }}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </AuthenticatedLayout>
  );
}