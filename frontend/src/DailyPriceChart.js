import React, { useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";
import dayjs from "dayjs";

export default function DailyPriceChart({ dailyData, range, setRange }) {
  const filteredData = useMemo(() => {
    if (!dailyData || dailyData.length === 0) return [];
    const cutoff = {
      "1M": dayjs().subtract(1, "month"),
      "1Y": dayjs().subtract(1, "year"),
      "5Y": dayjs().subtract(5, "year"),
      All: dayjs("1900-01-01"),
    }[range];
    return dailyData.filter((d) => dayjs(d.date).isAfter(cutoff));
  }, [dailyData, range]);

  const yDomain = useMemo(() => {
    if ((range === "1M" || range === "1Y") && filteredData.length > 1) {
      const prices = filteredData.map((d) => d.price).filter((v) => typeof v === "number" && isFinite(v));
      if (prices.length >= 2) {
        const min = Math.min(...prices);
        const max = Math.max(...prices);
        if (min !== max) {
          return [min * 0.95, max * 1.005];
        }
      }
    }
    return ["auto", "auto"];
  }, [filteredData, range]);

  return (
    <div className="bg-white p-6 rounded-lg shadow max-w-5xl mx-auto space-y-8">
      {/* Time range buttons */}
      <div className="flex flex-wrap gap-2">
        {["1M", "1Y", "5Y", "All"].map((label) => (
          <button
            key={label}
            onClick={() => setRange(label)}
            className={`px-4 py-1.5 rounded-md font-medium transition transform 
              ${
                range === label
                  ? "bg-blue-600 text-white shadow-md"
                  : "bg-gray-200 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600"
              }
              hover:scale-105 duration-200 ease-in-out
            `}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Chart + vertical label */}
      <div className="flex items-center gap-1">
        <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 w-1 text-center writing-mode-vertical rotate-180 whitespace-nowrap">
          Daily Price
        </div>

        <div className="flex-1">
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={filteredData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tickFormatter={(d) => dayjs(d).format("MM/DD")}
                angle={-45}
                textAnchor="end"
                height={40}
              />
              <YAxis domain={yDomain} tickFormatter={(val) => val.toFixed(0)} />
              <Tooltip />
              <Line type="monotone" dataKey="price" stroke="#3b82f6" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
