import React, { useState } from "react";

function StockTable({ data }) {
  const [sortOrder, setSortOrder] = useState("desc"); // 'desc' or 'asc'

  const sortedData = [...data].sort((a, b) => {
    return sortOrder === "desc"
      ? new Date(b.date) - new Date(a.date)
      : new Date(a.date) - new Date(b.date);
  });

  const toggleOrder = () => {
    setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
  };

  return (
    <div className="mb-8">
      {/* Toggle Button */}
      <div className="flex justify-end mb-2">
        <button
          onClick={toggleOrder}
          className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition"
        >
          Sort: {sortOrder === "desc" ? "Newest First" : "Oldest First"}
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="table-auto w-full text-sm text-gray-800 border-collapse shadow rounded-lg">
          <thead>
            <tr className="bg-gray-100 text-gray-700">
              <th className="px-4 py-3 text-left">Quarter</th>
              <th className="px-4 py-3 text-left">Date</th>
              <th className="px-4 py-3 text-right">EPS</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-right">TTM EPS</th>
              <th className="px-4 py-3 text-right">P/E</th>
            </tr>
          </thead>
          <tbody>
            {sortedData.map((row, i) => (
              <tr
                key={i}
                className={i % 2 === 0 ? "bg-white" : "bg-gray-50 hover:bg-blue-50"}
              >
                <td className="border-t px-4 py-2">{row.quarter}</td>
                <td className="border-t px-4 py-2">{row.date}</td>
                <td className="border-t px-4 py-2 text-right">{row.eps}</td>
                <td className="border-t px-4 py-2 text-right">{row.price}</td>
                <td className="border-t px-4 py-2 text-right">{row.ttm_eps ?? "N/A"}</td>
                <td className="border-t px-4 py-2 text-right">{row.pe_ratio ?? "N/A"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default StockTable;
