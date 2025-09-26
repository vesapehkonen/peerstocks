// src/StockCharts.js
import React, { useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend } from "recharts";

export default function StockCharts({ quarterlyData, yearRange }) {
  const filteredData = useMemo(() => {
    return quarterlyData?.slice(-yearRange * 4) || [];
  }, [quarterlyData, yearRange]);

  if (!filteredData.length) {
    return <div className="text-center text-gray-500">Loading or no data available</div>;
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow max-w-5xl mx-auto space-y-8">
      {/* Chart Row */}
      {[
        { label: "Stock Price", key: "price", color: "#3b82f6", showXAxis: false },
        { label: "TTM EPS", key: "ttm_eps", color: "#10b981", showXAxis: false },
        { label: "P/E Ratio", key: "pe_ratio", color: "#f97316", showXAxis: true },
      ].map(({ label, key, color, showXAxis }) => (
        <div key={key} className="flex items-center gap-1">
          {/* Vertical Label */}
          <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 w-3 text-center writing-mode-vertical rotate-180 whitespace-nowrap">
            {label}
          </div>

          {/* Chart */}
          <div className="flex-1">
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={filteredData} syncId="stockSync">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="quarter" angle={-45} textAnchor="end" interval={0} height={60} hide={!showXAxis} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey={key}
                  name={label}
                  stroke={color}
                  strokeOpacity={0.8}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ))}
    </div>
  );
}
