import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import DailyPriceChart from "./DailyPriceChart";
import StockCharts from "./StockCharts";
import StockTable from "./StockTable";
import api from "./api";

function StockDetailsPage() {
  const { ticker } = useParams();
  const [stockData, setStockData] = useState(null);
  const [yearRange, setYearRange] = useState(5);
  const [priceRange, setPriceRange] = useState("1Y");
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    if (ticker) {
      api
        .get(`/stocks/${ticker}`)
        .then((res) => setStockData(res.data))
        .catch((err) => console.error("Error fetching stock data:", err));

      api
        .get(`/ai-summary/${ticker}`)
        .then((res) => setSummary(res.data.summary))
        .catch((err) => console.error("Error fetching summary:", err));
    }
  }, [ticker]);

  return (
    <div className="max-w-5xl mx-auto bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 py-8 px-4">
      <h1 className="text-3xl font-bold mb-6 text-center">📊 {ticker} Stock Details</h1>
      {summary !== null && (
        <div className="bg-yellow-100 dark:bg-yellow-800 text-yellow-900 dark:text-yellow-100 rounded p-4 shadow mb-6">
          <h2 className="text-lg font-bold mb-2">🧠 AI Summary</h2>
          <p className="text-sm whitespace-pre-line">
            {String(summary).trim() || "No AI summary available right now."}
          </p>
        </div>
      )}

      {stockData?.quarterly?.length > 0 && (
        <div className="space-y-8">
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-700">Daily Stock Price</h2>
            <DailyPriceChart dailyData={stockData.daily_prices} range={priceRange} setRange={setPriceRange} />
          </div>

          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-700">Quarterly Overview</h2>
            <StockCharts
              quarterlyData={stockData.quarterly}
              dailyPriceData={stockData.daily_prices}
              yearRange={yearRange}
              setYearRange={setYearRange}
            />
          </div>

          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-700">Key Financials</h2>
            <StockTable data={stockData.quarterly} />
          </div>
        </div>
      )}
    </div>
  );
}

export default StockDetailsPage;
