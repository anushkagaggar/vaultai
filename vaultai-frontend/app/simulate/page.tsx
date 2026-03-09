'use client';
import { useState } from 'react';
import { Save } from 'lucide-react';
import AuthenticatedLayout from '../components/Authenticatedlayout';
import SimulateForm, { type SimulationParams } from '../components/SimulateForm';
import ProjectionChart from '../components/ProjectionChart';
import ScenarioComparison from '../components/ScenarioComparison';
import { formatIndianCurrency } from '../../lib/planUtils';
import type { ProjectionDataPoint, ScenarioResult } from '../../lib/types/plans';

interface SimResult {
  projection: ProjectionDataPoint[];
  finalBalance: number;
  monthsToGoal: number | null;
  coverageRatio: number;
}

export default function SimulatePage() {
  const [isLoading, setIsLoading]           = useState(false);
  const [currentResult, setCurrentResult]   = useState<SimResult | null>(null);
  const [savedScenarios, setSavedScenarios] = useState<ScenarioResult[]>([]);
  const [currentParams, setCurrentParams]   = useState<SimulationParams | null>(null);

  const handleSimulate = async (params: SimulationParams) => {
    setIsLoading(true);
    setCurrentParams(params);
    await new Promise((r) => setTimeout(r, 800));

    const projection: ProjectionDataPoint[] = [];
    for (let month = 1; month <= params.horizonMonths; month++) {
      const contribution = params.monthlySavings * month;
      const growth       = (contribution * params.annualRate / 100) * (month / 12);
      projection.push({ month, balance: contribution + growth, growth, contribution });
    }

    const finalBalance   = projection[projection.length - 1].balance;
    const coverageRatio  = finalBalance / params.targetAmount;
    const monthsToGoal   = projection.find((p) => p.balance >= params.targetAmount)?.month ?? null;

    setCurrentResult({ projection, finalBalance, monthsToGoal, coverageRatio });
    setIsLoading(false);
  };

  const handleSave = () => {
    if (!currentResult || !currentParams) return;
    setSavedScenarios((prev) => [
      ...prev,
      {
        label:            currentParams.scenarioLabel || `Scenario ${prev.length + 1}`,
        finalBalance:     currentResult.finalBalance,
        totalContributed: currentParams.monthlySavings * currentParams.horizonMonths,
        totalGrowth:      currentResult.finalBalance - currentParams.monthlySavings * currentParams.horizonMonths,
        monthsToGoal:     currentResult.monthsToGoal,
      },
    ]);
  };

  return (
    <AuthenticatedLayout title="What-If Simulator">
      <p style={{ fontSize: 13, color: '#94A3B8', marginBottom: 24 }}>
        Test different scenarios and compare outcomes
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Form */}
        <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#F1F5F9', margin: '0 0 20px' }}>
            Simulation Parameters
          </h2>
          <SimulateForm onSimulate={handleSimulate} isLoading={isLoading} />
        </div>

        {/* Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {currentResult ? (
            <>
              <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                  <h2 style={{ fontSize: 16, fontWeight: 700, color: '#F1F5F9', margin: 0 }}>Results</h2>
                  <button
                    onClick={handleSave}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, background: '#22263A', border: '1px solid #6366F1', color: '#6366F1', cursor: 'pointer' }}
                  >
                    <Save size={12} /> Save Scenario
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 3px' }}>Final Balance at Horizon</p>
                    <p style={{ fontSize: 24, fontWeight: 800, color: '#6366F1', margin: 0, fontFamily: 'monospace' }}>
                      {formatIndianCurrency(currentResult.finalBalance)}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 3px' }}>Months to Reach Target</p>
                    <p style={{ fontSize: 16, fontWeight: 700, color: '#F1F5F9', margin: 0 }}>
                      {currentResult.monthsToGoal !== null
                        ? `${currentResult.monthsToGoal} months`
                        : 'Not reachable in horizon'}
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: 11, color: '#94A3B8', margin: '0 0 3px' }}>Coverage Ratio</p>
                    <p style={{ fontSize: 16, fontWeight: 700, color: currentResult.coverageRatio >= 1 ? '#10B981' : '#F59E0B', margin: 0 }}>
                      {Math.round(currentResult.coverageRatio * 100)}%
                    </p>
                  </div>
                </div>
              </div>

              <ProjectionChart
                data={currentResult.projection}
                targetAmount={currentParams?.targetAmount}
                label="Projection"
              />
            </>
          ) : (
            <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 48, textAlign: 'center' }}>
              <p style={{ fontSize: 14, color: '#94A3B8', margin: 0 }}>Run a simulation to see results</p>
            </div>
          )}
        </div>
      </div>

      {/* Scenario comparison */}
      {savedScenarios.length >= 2 && (
        <div style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#F1F5F9', marginBottom: 8 }}>Saved Scenarios</h2>
          <p style={{ fontSize: 13, color: '#94A3B8', marginBottom: 16 }}>Compare your saved scenarios side by side</p>
          <ScenarioComparison scenarios={savedScenarios} />
        </div>
      )}

      {savedScenarios.length === 1 && (
        <div style={{ marginTop: 24, background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 20, textAlign: 'center' }}>
          <p style={{ fontSize: 13, color: '#94A3B8', margin: 0 }}>Save one more scenario to enable comparison</p>
        </div>
      )}
    </AuthenticatedLayout>
  );
}