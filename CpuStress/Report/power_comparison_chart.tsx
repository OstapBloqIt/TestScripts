import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

export default function PowerComparisonChart() {
  const data = [
    {
      metric: 'Average Power',
      '2-Core 1GB': 6.56,
      '4-Core 2GB': 7.40,
      unit: 'W'
    },
    {
      metric: 'Peak Power',
      '2-Core 1GB': 8.24,
      '4-Core 2GB': 8.96,
      unit: 'W'
    },
    {
      metric: 'Min Power',
      '2-Core 1GB': 4.85,
      '4-Core 2GB': 5.98,
      unit: 'W'
    },
    {
      metric: '95th Percentile',
      '2-Core 1GB': 5.82,
      '4-Core 2GB': 6.72,
      unit: 'W'
    }
  ];

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-4 border-2 border-gray-300 rounded shadow-lg">
          <p className="font-semibold text-gray-900 mb-2">{label}</p>
          {payload.map((entry, index) => (
            <p key={index} style={{ color: entry.color }} className="text-sm">
              {entry.name}: <strong>{entry.value}W</strong>
            </p>
          ))}
          {payload.length === 2 && (
            <p className="text-sm text-orange-600 font-semibold mt-2 pt-2 border-t">
              Delta: +{(payload[1].value - payload[0].value).toFixed(2)}W 
              (+{(((payload[1].value / payload[0].value) - 1) * 100).toFixed(1)}%)
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full h-screen bg-white p-8 flex items-center justify-center">
      <div className="w-full max-w-5xl">
        <div className="mb-6">
          <h2 className="text-3xl font-bold text-gray-900 mb-2">
            Power Consumption Comparison
          </h2>
          <p className="text-lg text-gray-600">
            Dual-core 1GB vs Quad-core 2GB SoM
          </p>
        </div>

        <ResponsiveContainer width="100%" height={500}>
          <BarChart 
            data={data}
            margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis 
              dataKey="metric" 
              tick={{ fill: '#374151', fontSize: 14 }}
              angle={0}
              textAnchor="middle"
            />
            <YAxis 
              label={{ 
                value: 'Power Consumption (Watts)', 
                angle: -90, 
                position: 'insideLeft',
                style: { fill: '#374151', fontSize: 16, fontWeight: 600 }
              }}
              tick={{ fill: '#374151', fontSize: 14 }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend 
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="rect"
              iconSize={16}
            />
            <Bar 
              dataKey="2-Core 1GB" 
              fill="#3b82f6" 
              radius={[8, 8, 0, 0]}
              label={{ position: 'top', fill: '#1e40af', fontSize: 13, fontWeight: 600 }}
            />
            <Bar 
              dataKey="4-Core 2GB" 
              fill="#10b981" 
              radius={[8, 8, 0, 0]}
              label={{ position: 'top', fill: '#065f46', fontSize: 13, fontWeight: 600 }}
            />
          </BarChart>
        </ResponsiveContainer>

        <div className="mt-6 grid grid-cols-4 gap-4">
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4">
            <div className="text-xs text-blue-700 font-semibold uppercase mb-1">2-Core Average</div>
            <div className="text-2xl font-bold text-blue-900">6.56W</div>
          </div>
          <div className="bg-green-50 border-l-4 border-green-500 p-4">
            <div className="text-xs text-green-700 font-semibold uppercase mb-1">4-Core Average</div>
            <div className="text-2xl font-bold text-green-900">7.40W</div>
          </div>
          <div className="bg-orange-50 border-l-4 border-orange-500 p-4">
            <div className="text-xs text-orange-700 font-semibold uppercase mb-1">Power Delta</div>
            <div className="text-2xl font-bold text-orange-900">+0.84W</div>
          </div>
          <div className="bg-purple-50 border-l-4 border-purple-500 p-4">
            <div className="text-xs text-purple-700 font-semibold uppercase mb-1">Increase</div>
            <div className="text-2xl font-bold text-purple-900">+12.8%</div>
          </div>
        </div>

        <div className="mt-6 bg-green-50 border border-green-300 rounded-lg p-4">
          <p className="text-sm text-green-900">
            <strong>Key Insight:</strong> The 4-core configuration adds only 0.84W average power consumption 
            (+12.8%) while delivering 2x compute cores, demonstrating excellent power scaling efficiency.
          </p>
        </div>
      </div>
    </div>
  );
}