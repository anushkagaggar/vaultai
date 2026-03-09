'use client';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent';
import { formatIndianCurrency } from '../../lib/planUtils';

interface AllocationWheelProps {
  equity: number;
  debt: number;
  liquid: number;
  monthlyAmount: number;
}

const COLORS = ['#6366F1', '#F59E0B', '#14B8A6'];

export default function AllocationWheel({ equity, debt, liquid, monthlyAmount }: AllocationWheelProps) {
  const data = [
    { name: 'Equity', value: equity, amount: Math.round(monthlyAmount * equity / 100) },
    { name: 'Debt',   value: debt,   amount: Math.round(monthlyAmount * debt / 100) },
    { name: 'Liquid', value: liquid, amount: Math.round(monthlyAmount * liquid / 100) },
  ];

  // Fix: use ValueType / NameType to match Recharts Formatter signature
  const tooltipFormatter = (value: ValueType, name: NameType) =>
    [`${value}%`, String(name)] as [string, string];

  return (
    <div style={{ background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 12, padding: 24 }}>
      <p style={{ fontSize: 11, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 20px' }}>
        Allocation Wheel
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
        <ResponsiveContainer width={200} height={200}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((_, index) => (
                <Cell key={index} fill={COLORS[index]} />
              ))}
            </Pie>
            <Tooltip
              formatter={tooltipFormatter}
              contentStyle={{
                background: '#22263A',
                border: '1px solid #2E3248',
                borderRadius: 8,
                color: '#F1F5F9',
                fontSize: 12,
              }}
            />
          </PieChart>
        </ResponsiveContainer>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {data.map((d, i) => (
            <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 12, height: 12, borderRadius: 3, background: COLORS[i], flexShrink: 0 }} />
              <div>
                <p style={{ fontSize: 13, fontWeight: 600, color: '#F1F5F9', margin: 0 }}>{d.name}</p>
                <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, fontFamily: 'monospace' }}>
                  {d.value}% · {formatIndianCurrency(d.amount)}/mo
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}