// App.js
import React, { useState, useEffect } from "react";
import axios from "axios";
import SearchForm from "./SearchForm";
import StockTable from "./StockTable";
import StockCharts from "./StockCharts";
import DailyPriceChart from "./DailyPriceChart";
import { Link, Routes, Route } from "react-router-dom";
import AdvancedSearch from "./AdvancedSearch";
import StockDetailsPage from "./StockDetailsPage";
import ComparePage from "./ComparePage";
import SiteHeader from "./SiteHeader";
import TrendingTickers from "./TrendingTickers";
import StockHeader from "./StockHeader";
import api from "./api";

function HomePage() {
  const [ticker, setTicker] = useState(null);
  const [stockData, setStockData] = useState(null);
  const [yearRange, setYearRange] = useState(5);
  const [priceRange, setPriceRange] = useState("1Y");

  useEffect(() => {
    if (!ticker) return;
    const ctrl = new AbortController();
    api
      .get(`/stocks/${ticker}`, { signal: ctrl.signal })
      .then((res) => setStockData(res.data))
      .catch((err) => {
        if (err.name !== "CanceledError" && err.message !== "canceled") {
          console.error("Error fetching stock data:", err);
        }
      });
    return () => ctrl.abort();
  }, [ticker]);

  return (
    <div className="max-w-5xl mx-auto bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 py-4 px-4">
      <div className="flex flex-col items-center text-center mb-3">
        <h1 className="text-lg sm:text-xl font-semibold">Quick stock lookup.</h1>

        <p className="text-sm text-gray-500 dark:text-gray-400">
          Price, EPS and P/E history for one ticker.{" "}
          <Link to="/advanced-search" className="text-blue-600 dark:text-blue-400 hover:underline">
            Advanced Search
          </Link>{" "}
          for multi-stock screening.
        </p>
      </div>

      <div className="mb-6 flex justify-center">
        <SearchForm onSearch={setTicker} />
      </div>

      <div className="mb-4">
        <TrendingTickers onSelect={(sym) => setTicker(sym)} />
      </div>

      {/* Data sections shown after a ticker is selected */}
      <div className="space-y-4">
        {stockData?.quarterly?.length > 0 && (
          <>
            {stockData && (
              <StockHeader ticker={ticker} metadata={stockData.metadata} dailyPrices={stockData.daily_prices} />
            )}

            <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
              <h2 className="text-xl font-semibold mb-2 text-gray-700 dark:text-gray-100">Daily Stock Price</h2>
              <DailyPriceChart dailyData={stockData.daily_prices} range={priceRange} setRange={setPriceRange} />
            </div>

            <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
              <h2 className="text-xl font-semibold mb-4 text-gray-700 dark:text-gray-100">Quarterly Overview</h2>
              <StockCharts
                quarterlyData={stockData.quarterly}
                dailyPriceData={stockData.daily_prices}
                yearRange={yearRange}
                setYearRange={setYearRange}
              />
            </div>

            <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
              <h2 className="text-xl font-semibold mb-4 text-gray-700 dark:text-gray-100">Key Financials</h2>
              <StockTable data={stockData.quarterly} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function AppWrapper() {
  return (
    <>
      <SiteHeader />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/advanced-search" element={<AdvancedSearch />} />
        <Route path="/stock/:ticker" element={<StockDetailsPage />} />
        <Route path="/compare" element={<ComparePage />} />
      </Routes>
    </>
  );
}

export default AppWrapper;
