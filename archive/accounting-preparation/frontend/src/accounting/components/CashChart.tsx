import React from 'react';
import { AreaChart, Area, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartNoAxesCombined } from 'lucide-react';
import { rupiah, shortMoney } from '../lib';

export const CashChart = ({ report }: any) => {
  const hasActivity = report.series.some((d: any) => d.income || d.outgoing);
  return <div className={`chart-area ${hasActivity ? '' : 'chart-is-empty'}`} data-testid="cash-flow-chart"><ResponsiveContainer width="100%" height={230}><AreaChart data={report.series} margin={{ top: 18, right: 15, left: 0, bottom: 0 }}>
    <defs><linearGradient id="incomeFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2563eb" stopOpacity={0.19} /><stop offset="100%" stopColor="#2563eb" stopOpacity={0.01} /></linearGradient></defs>
    <CartesianGrid strokeDasharray="4 5" vertical={false} stroke="#e8edf4" /><XAxis dataKey="date" tickFormatter={d => String(Number(d.slice(-2)))} interval={6} axisLine={false} tickLine={false} tick={{ fill: '#94a0b3', fontSize: 10 }} dy={8} /><YAxis tickFormatter={v => v === 0 ? '0' : shortMoney(v)} axisLine={false} tickLine={false} width={52} tick={{ fill: '#94a0b3', fontSize: 10 }} domain={hasActivity ? ['auto', 'auto'] : [0, 1000000]} />
    {hasActivity && <Tooltip formatter={(value: any, name: any) => [rupiah(value), name === 'income' ? 'Kas masuk' : 'Kas keluar']} labelFormatter={value => `Tanggal ${value}`} contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }} />}
    <Area type="monotone" dataKey="income" stroke={hasActivity ? '#2563eb' : 'transparent'} fill="url(#incomeFill)" strokeWidth={2.5} /><Area type="monotone" dataKey="outgoing" stroke={hasActivity ? '#e6a05b' : 'transparent'} fill="transparent" strokeWidth={2} />
  </AreaChart></ResponsiveContainer>{!hasActivity && <div className="chart-empty-label" data-testid="chart-empty-message"><ChartNoAxesCombined size={24} strokeWidth={1.4} /><strong>Perjalanan keuangan dimulai di sini</strong><span>Grafik akan terisi setelah ada pergerakan kas.</span></div>}</div>;
};