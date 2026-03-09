export type PlanType = 'budget' | 'invest' | 'goal' | 'simulate';
export type ValidationStatus = 'validated' | 'fallback';
export type FeasibilityLabel = 'FEASIBLE' | 'STRETCH' | 'INFEASIBLE';
export type RiskProfile = 'Conservative' | 'Moderate' | 'Aggressive';
export type ExternalFreshness = 'live' | 'cached' | 'fallback';
export type AssumptionRisk = 'low' | 'medium' | 'high';

export interface PlanConfidence {
  overall: number;
  dataCoverage: number;
  assumptionRisk: AssumptionRisk;
  externalFreshness: ExternalFreshness;
}

export interface GraphNode {
  name: string;
  type: 'validation' | 'llm' | 'simulation' | 'persist';
  status: 'success' | 'failed';
  description: string;
}

export interface BasePlan {
  id: string;
  planType: PlanType;
  userId: string;
  createdAt: string;
  validationStatus: ValidationStatus;
  confidence: PlanConfidence;
  degraded: boolean;
  graphTrace: GraphNode[];
  explanation: string;
  assumptions: Record<string, unknown>;
  constraints?: Record<string, unknown>;
}

export interface ProjectionDataPoint {
  month: number;
  balance: number;
  growth: number;
  contribution: number;
}

export interface ScenarioResult {
  label: string;
  finalBalance: number;
  totalContributed: number;
  totalGrowth: number;
  monthsToGoal: number | null;
}

export interface BudgetPlan extends BasePlan {
  planType: 'budget';
  incomeMonthly: number;
  inflationRate: number;
  minSavingsRate: number;
  monthlySavings: number;
  annualSavings: number;
  projection: ProjectionDataPoint[];
  scenarios: {
    base: ScenarioResult;
    optimistic: ScenarioResult;
    conservative: ScenarioResult;
  };
}

export interface InvestPlan extends BasePlan {
  planType: 'invest';
  riskProfile: RiskProfile;
  monthlyAmount: number;
  allocation: { equity: number; debt: number; liquid: number };
  amounts: { equity: number; debt: number; liquid: number };
}

export interface DebtPayoffRow {
  month: number;
  openingBalance: number;
  interest: number;
  principal: number;
  closingBalance: number;
}

export interface SubGoal {
  name: string;
  targetAmount: number;
  monthlyAllocated: number;
  feasibility: FeasibilityLabel;
}

export interface GoalPlan extends BasePlan {
  planType: 'goal';
  goalType: string;
  targetAmount: number;
  horizonMonths: number;
  projectedBalance: number;
  coverageRatio: number;
  feasibilityLabel: FeasibilityLabel;
  gapAmount?: number;
  monthsToGoal?: number | null;
  projection: ProjectionDataPoint[];
  adjustedTimeline?: { originalHorizon: number; adjustedHorizon: number; reason: string };
  debtPayoffSchedule?: DebtPayoffRow[];
  multiGoal?: { totalGoals: number; goals: SubGoal[] };
}

export interface SimulatePlan extends BasePlan {
  planType: 'simulate';
  scenarioLabel?: string;
  incomeMonthly: number;
  monthlySavings: number;
  targetAmount: number;
  horizonMonths: number;
  annualRate: number;
  finalBalance: number;
  totalContributed: number;
  totalGrowth: number;
  monthsToGoal: number | null;
  coverageRatio: number;
  projection: ProjectionDataPoint[];
}

export type Plan = BudgetPlan | InvestPlan | GoalPlan | SimulatePlan;

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  plan?: Plan;
}

export interface ChatRequest {
  message: string;
  userId: string;
}

export interface ChatResponse {
  message: string;
  plan?: Plan;
  thinking?: string;
  currentNode?: string;
}