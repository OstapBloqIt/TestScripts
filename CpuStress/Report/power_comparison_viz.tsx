import React from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export default function PowerComparisonCharts() {
  const summaryData = [
    {
      metric: 'Power (W)',
      '2-Core 1GB': 6.56,
      '4-Core 2GB': 7.40,
      delta: '+0.84W'
    },
    {
      metric: 'Temperature (C)',
      '2-Core 1GB': 46.87,
      '4-Core 2GB': 54.44,
      delta: '+7.57C'
    },
    {
      metric: 'Power/Core (W)',
      '2-Core 1GB': 3.28,
      '4-Core 2GB': 1.85,
      delta: '-1.43W'
    }
  ];

  const efficiencyData = [
    { name: '2-Core 1GB', value: 3.28, label: '3.28 W/core' },
    { name: '4-Core 2GB', value: 1.85, label: '1.85 W/core' }
  ];

  const powerDistData = [
    { range: '4.5-5.5W', '2-Core': 0, '4-Core': 0 },
    { range: '5.5-6.5W', '2-Core': 45, '4-Core': 15 },
    { range: '6.5-7.5W', '2-Core': 50, '4-Core': 70 },
    { range: '7.5-8.5W', '2-Core': 5, '4-Core': 15 },
    { range: '8.5-9.0W', '2-Core': 0, '4-Core': 0 }
  ];

  const tempDistData = [
    { range: '46C', '2-Core': 40, '4-Core': 0 },
    { range: '47C', '2-Core': 30, '4-Core': 0 },
    { range: '48C', '2-Core': 30, '4-Core': 0 },
    { range: '54C', '2-Core': 0, '4-Core': 60 },
    { range: '55C', '2-Core': 0, '4-Core': 40 }
  ];

  return (
    <div className="w-full p-6 bg-gray-50">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="bg-white p-6 rounded-lg shadow">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            SoM Power Consumption Analysis
          </h1>
          <p className="text-gray-600">
            Comparative analysis: Dual-core 1GB vs Quad-core 2GB under sustained load
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500 mb-1">Average Power</div>
            <div className="text-3xl font-bold text-blue-600 mb-2">+0.84W</div>
            <div className="text-sm text-gray-600">6.56W to 7.40W (+12.8%)</div>
            <div className="mt-3 text-xs text-gray-500">4-Core draws slightly more total power</div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500 mb-1">Per-Core Efficiency</div>
            <div className="text-3xl font-bold text-green-600 mb-2">-43.6%</div>
            <div className="text-sm text-gray-600">3.28W to 1.85W per core</div>
            <div className="mt-3 text-xs text-gray-500">Much better power efficiency per core</div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500 mb-1">Temperature Delta</div>
            <div className="text-3xl font-bold text-orange-600 mb-2">+7.6C</div>
            <div className="text-sm text-gray-600">46.9C to 54.4C</div>
            <div className="mt-3 text-xs text-gray-500">Higher thermal output under load</div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Average Power Consumption by Configuration
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={summaryData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="metric" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="2-Core 1GB" fill="#3b82f6" />
              <Bar dataKey="4-Core 2GB" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Power Efficiency: Per-Core Power Consumption
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={efficiencyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis label={{ value: 'Watts per Core', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Bar dataKey="value" fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded">
            <p className="text-sm text-green-800">
              <strong>Efficiency Winner:</strong> The 4-Core configuration is 43.6% more power-efficient per core (1.85W vs 3.28W per core)
            </p>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Power Consumption Distribution
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={powerDistData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="range" />
              <YAxis label={{ value: 'Sample Count', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="2-Core" fill="#3b82f6" />
              <Bar dataKey="4-Core" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Temperature Distribution Under Load
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={tempDistData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="range" />
              <YAxis label={{ value: 'Sample Count', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="2-Core" fill="#3b82f6" />
              <Bar dataKey="4-Core" fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Detailed Comparison Summary
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Metric</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">2-Core 1GB</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">4-Core 2GB</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Delta</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Average Power</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">6.56W</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">7.40W</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-orange-600">+0.84W (+12.8%)</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Peak Power</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">8.24W</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">8.96W</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-orange-600">+0.72W</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Power per Core</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">3.28W</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">1.85W</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600">-1.43W (-43.6%)</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Average Temperature</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">46.9C</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">54.4C</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-orange-600">+7.5C</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Peak Temperature</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">48C</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">55C</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-orange-600">+7C</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-3">Key Findings</h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li>• The 4-Core SoM uses only 12.8% more total power while providing 2x the cores</li>
            <li>• Per-core efficiency improves dramatically by 43.6% (1.85W vs 3.28W per core)</li>
            <li>• Temperature increases by 7.6C under sustained load, but remains within safe limits</li>
            <li>• Both configurations sustained 90%+ CPU utilization throughout testing</li>
            <li>• Voltage remains stable around 12.5V for both configurations</li>
          </ul>
        </div>
      </div>
    </div>
  );
}