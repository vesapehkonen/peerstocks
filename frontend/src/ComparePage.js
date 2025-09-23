import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  BarChart,
  Bar,    
} from "recharts";

import api from "./api";
import { Link } from "react-router-dom";

const TICKER_PALETTE = [
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
  "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
  "#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2",
  "#edc949", "#af7aa1", "#ff9da7", "#9c755f", "#bab0ab",
];

const chipBase =
  "px-3 py-1.5 rounded-full border text-sm transition focus:outline-none focus:ring-2 focus:ring-blue-500";
const chipOn =
  "bg-blue-600 text-white border-blue-600 hover:bg-blue-700";
const chipOff =
  "bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600";

function safeGetLocalStorage(key, fallback) {
  try {
    if (typeof window === "undefined") return fallback;
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function safeSetLocalStorage(key, value) {
  try {
    if (typeof window === "undefined") return;
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

export function useTickerColors(keys) {
  const [map, setMap] = useState(() => safeGetLocalStorage("tickerColors", {}));

  useEffect(() => {
    const used = new Set(Object.values(map));
    const next = { ...map };

    keys.forEach((k) => {
      if (!next[k]) {
        const color =
          TICKER_PALETTE.find((c) => !used.has(c)) ||
          `hsl(${Math.floor((Object.keys(next).length * 137.508) % 360)} 70% 45%)`;
        next[k] = color;
        used.add(color);
      }
    });

    if (JSON.stringify(next) !== JSON.stringify(map)) {
      setMap(next);
      safeSetLocalStorage("tickerColors", next);
    }
  }, [keys]);

  useEffect(() => {
    const filtered = {};
    keys.forEach((k) => {
      if (map[k]) filtered[k] = map[k];
    });
    if (JSON.stringify(filtered) !== JSON.stringify(map)) {
      safeSetLocalStorage("tickerColors", filtered);
    }
  }, [keys, map]);

  return map;
}

const RANGES = ["3M", "1Y", "5Y", "ALL"];

function toDate(d) {
  if (d instanceof Date) return d;
  if (typeof d === "number") return new Date(d);
  return new Date(String(d));
}

function cutoffDateForRange(range) {
  const now = new Date();
  switch (range) {
    case "3M": return new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
    case "1Y": return new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
    case "5Y": return new Date(now.getFullYear() - 5, now.getMonth(), now.getDate());
    case "ALL": return null;
    default: return new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
  }
}

function filterByRange(points, range) {
  if (!points?.length) return [];
  const cut = cutoffDateForRange(range);
  if (!cut) return points;
  const c = +cut;
  return points.filter((p) => {
    const t = +toDate(p.date);
    return Number.isFinite(t) && t >= c;
  });
}

function indexPrice(points, range) {
  const win = filterByRange(points, range);
  if (!win.length) return [];
  const base = win[0].close;
  if (!base || !Number.isFinite(base)) return [];
  return win.map((p) => ({ date: String(p.date), v: (p.close / base) * 100 }));
}

function mapPE(points, range) {
  const win = filterByRange(points, range)
    .filter((p) => p.pe != null && Number.isFinite(Number(p.pe)) && Number(p.pe) > 0);
  return win.map((p) => ({ date: String(p.date), v: Number(p.pe) }));
}

function mapEPS(points, range) {
  const win = filterByRange(points, range)
    .filter((p) => p != null && p.eps != null && Number.isFinite(Number(p.eps)));
  return win.map((p) => ({ date: String(p.date), v: Number(p.eps) }));
}

function deriveSeries(stocks, range) {
  return (stocks ?? []).map((s) => {
    const pts = (s.prices ?? []).filter((p) => p?.date != null && p?.close != null);
    const win = filterByRange(pts, range);
    const priceIdx = indexPrice(pts, range);
    const pe = mapPE(pts, range);
    const eps = mapEPS(pts, range);
    const coverage = {
      first: win.length ? String(win[0].date) : null,
      last: win.length ? String(win[win.length - 1].date) : null,
    };
    const growth = {
      revenue_growth_1y: s.revenue_growth_1y,
      revenue_growth_3y: s.revenue_growth_3y,
      revenue_growth_5y: s.revenue_growth_5y,
      price_growth_5y: s.price_growth_5y,
    };
    const lastClose = win.length ? Number(win[win.length - 1].close) : null;
    return { t: s.ticker, priceIdx, pe, eps, coverage, growth, lastClose };
  });
}

const fmtPctFrom100 = (v) => `${(v - 100).toFixed(1)}%`;

const fmtNum = (v) => {
  if (v == null || !Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e12) return (v / 1e12).toFixed(2) + "T";
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (abs >= 1e3) return (v / 1e3).toFixed(2) + "K";
  return String(+v.toFixed(2));
};

function useCompareUrlState(opts) {
  const getParams = useCallback(() => new URLSearchParams(window.location.search), []);

  const [tickers, setTickers] = useState(() => {
    const p = getParams();
    const s = p.get("tickers");
    if (s) return s.split(",").filter(Boolean).slice(0, 6);
    return opts?.initialTickers ?? [];
  });

  const [range, setRange] = useState(() => {
    const p = getParams();
    const r = (p.get("range")) || opts?.initialRange || "1Y";
    return (RANGES.includes(r) ? r : "1Y");
  });

  const [clipPE, setClipPE] = useState(() => getParams().get("clipPE") === "true");

  useEffect(() => {
    const p = getParams();
    if (tickers.length) p.set("tickers", tickers.join(",")); else p.delete("tickers");
    p.set("range", range);
    p.set("clipPE", String(clipPE));
    const qs = p.toString();
    const next = `${window.location.pathname}?${qs}`;
    window.history.replaceState({}, "", next);
  }, [tickers, range, clipPE, getParams]);

  return { tickers, setTickers, range, setRange, clipPE, setClipPE };
}

function useStockSeries(tickers, range, fetchStocks) {
  const [stocks, setStocks] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();

    (async () => {
      setLoading(true);
      setError(null);
      try {
        let data;
        if (fetchStocks) {
          data = await fetchStocks(tickers);
        } else {
          const resp = await api.get("/stocks", {
            signal: ctrl.signal,
            params: { tickers },
            paramsSerializer: {
              serialize: (p) =>
              (p.tickers || [])
                .map(t => `tickers=${encodeURIComponent(t)}`)
                .join("&"),
            },
          });
          const raw = resp.data;
          data = Array.isArray(raw)
            ? raw
            : Object.entries(raw || {}).map(([ticker, v]) => ({
              ticker,
              ...(v?.prices ? v : { prices: v }),
            }));
        }
        if (!cancelled) setStocks(data);
      } catch (e) {
        if (!cancelled && e.name !== "CanceledError" && e.message !== "canceled") {
          setError(e?.message ?? "Failed to load");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    
    return () => { cancelled = true; ctrl.abort(); };
  }, [tickers, fetchStocks]);

  const derived = useMemo(() => deriveSeries(stocks ?? [], range), [stocks, range]);
  return { stocks: stocks ?? [], derived, loading, error };
}

function mergeByDate(derived, key /* 'priceIdx' or 'pe' */) {
  const byDate = new Map();
  derived.forEach(d => {
    (d[key] || []).forEach(p => {
      const date = String(p.date);
      if (!byDate.has(date)) byDate.set(date, { date });
      byDate.get(date)[d.t] = p.v; // put each ticker's value under its symbol
    });
  });
  return Array.from(byDate.values()).sort(
    (a, b) => new Date(a.date) - new Date(b.date)
  );
}

export default function ComparePage({ fetchStocks, initialTickers, initialRange }) {
  const { tickers, setTickers, range, setRange, clipPE, setClipPE } = useCompareUrlState({ initialTickers, initialRange });
  const { derived, loading, error } = useStockSeries(tickers, range, fetchStocks);

  const [hidden, setHidden] = useState({});
  const toggleSeries = useCallback((t, isolate = false) => {
    setHidden((h) => {
      if (isolate) {
        const allHidden = {};
        derived.forEach((d) => { allHidden[d.t] = d.t !== t; });
        return allHidden;
      }
      return { ...h, [t]: !h[t] };
    });
  }, [derived]);

  const [showPrice, setShowPrice] = useState(true);
  const [showPE, setShowPE] = useState(true);
  const [showEPS, setShowEPS] = useState(true);
    
  const colors = useTickerColors(derived.map(d => d.t));

  return (
    <div className="max-w-5xl mx-auto bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 py-8 px-4 space-y-6">	
      <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-4">
        <Header
          tickers={tickers}
          setTickers={setTickers}
          range={range}
          setRange={setRange}
          clipPE={clipPE}
          setClipPE={setClipPE}
          colors={colors}
        />

{/* Chart visibility (chip-style) */}
<div className="bg-white dark:bg-gray-800 shadow rounded-lg p-3 mb-2">
  <div className="flex flex-wrap items-center gap-2 text-sm">
    <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mr-1">
      Charts
    </span>

    <button
      onClick={() => setShowPrice(v => !v)}
      className={`${chipBase} ${showPrice ? chipOn : chipOff}`}
      aria-pressed={showPrice}
      title={showPrice ? "Hide Price" : "Show Price"}
    >
      Price
    </button>

    <button
      onClick={() => setShowPE(v => !v)}
      className={`${chipBase} ${showPE ? chipOn : chipOff}`}
      aria-pressed={showPE}
      title={showPE ? "Hide P/E" : "Show P/E"}
    >
      P/E
    </button>

    <button
      onClick={() => setShowEPS(v => !v)}
      className={`${chipBase} ${showEPS ? chipOn : chipOff}`}
      aria-pressed={showEPS}
      title={showEPS ? "Hide EPS" : "Show EPS"}
    >
      EPS
    </button>
  </div>
</div>
      </div>

      {error && <div className="text-red-600 text-sm">{error}</div>}
      {loading && <div className="text-sm opacity-70">Loading…</div>}

 {showPrice && (
   <MergedPriceChart
     derived={derived}
     range={range}
     colors={colors}
     hidden={hidden}
     onLegend={toggleSeries}
   />
 )}
 {showPE && (
   <MergedPEChart
     derived={derived}
     range={range}
     colors={colors}
     hidden={hidden}
     onLegend={toggleSeries}
     clipPE={clipPE}
   />
 )}
 {showEPS && <EPSGrid derived={derived} range={range} colors={colors} />}

      <CompareTable derived={derived} range={range} />
    </div>
  );
}

function Header({ tickers, setTickers, range, setRange, clipPE, setClipPE, colors }) {
  const [input, setInput] = useState("");
  const addTicker = () => {
    const t = input.trim().toUpperCase();
    if (!t) return;
    if (tickers.includes(t)) { setInput(""); return; }
    setTickers([...tickers, t].slice(0, 6));
    setInput("");
  };
  const removeTicker = (t) => setTickers(tickers.filter((x) => x !== t));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {tickers.map((t) => (
          <span
            key={t}
            className="inline-flex items-center gap-2 px-2 py-1 rounded-full text-sm"
            style={{ background: (colors[t] || "#999") + "20", color: colors[t] || "#999" }}
          >
            {t}
            <button onClick={() => removeTicker(t)} className="text-xs opacity-70 hover:opacity-100">✕</button>
          </span>
        ))}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") addTicker(); }}
          placeholder="Add ticker…"
          className="border rounded px-2 py-1 text-sm dark:bg-gray-800 dark:text-gray-100 dark:border-gray-600"
          style={{ minWidth: 140 }}
        />
        <button onClick={addTicker} className="text-sm px-2 py-1 border rounded">Add</button>
      </div>

      <div className="flex items-center gap-3">
        <div className="inline-flex bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
          {RANGES.map((r) => (
            <button key={r} onClick={() => setRange(r)} className={`px-3 py-1 text-sm ${range === r ? "bg-white border border-gray-300" : "opacity-70"}`}>{r}</button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={clipPE} onChange={(e) => setClipPE(e.target.checked)} />
          Clip P/E outliers
        </label>
      </div>
    </div>
  );
}

function MergedPriceChart({ derived, range, colors, hidden, onLegend }) {
  const data = React.useMemo(() => mergeByDate(derived, 'priceIdx'), [derived, range]);
  const syncId = "cmp";
  return (
    <section className="bg-white dark:bg-gray-800 shadow rounded-lg p-4">
      <h3 className="text-sm font-medium mb-1">Price (Indexed = 100)</h3>
      <div className="h-72 w-full">
        <ResponsiveContainer>
          <LineChart
            key={`price-${range}`}
            data={data}
            syncId={syncId}
            margin={{ top: 8, right: 18, left: 8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" type="category" hide />
            <YAxis tickFormatter={fmtPctFrom100} domain={["auto", "auto"]} width={60} />
            <Tooltip formatter={(v) => fmtPctFrom100(Number(v))} />
            <Legend onClick={(e) => onLegend(e?.value)} onDoubleClick={(e) => onLegend(e?.value, true)} />
            {derived.map((s) => (
              <Line
                key={s.t}
                name={s.t}
                type="monotone"
                dataKey={s.t}
                stroke={colors[s.t]}
                strokeWidth={hidden[s.t] ? 1 : 2}
                opacity={hidden[s.t] ? 0.25 : 1}
                dot={false}
                isAnimationActive={false}
		connectNulls  
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function MergedPEChart({ derived, range, colors, hidden, onLegend, clipPE }) {
  const syncId = "cmp";
  const data = React.useMemo(() => mergeByDate(derived, 'pe'), [derived, range]);

  const domain = useMemo(() => {
    if (!clipPE) return ["auto", "auto"];

    // collect clean numeric values only
    const vals = [];
    derived?.forEach(d => (d.pe || []).forEach(p => {
      const v = Number(p?.v);
      if (Number.isFinite(v)) vals.push(v);
    }));
    
    if (vals.length < 5) return ["auto", "auto"]; // not enough to clip
    
    vals.sort((a, b) => a - b);
    const i5 = Math.floor(0.05 * (vals.length - 1));
    const i95 = Math.floor(0.95 * (vals.length - 1));
    const p5 = vals[i5];
    const p95 = vals[i95];
    
    // guard: invalid/degenerate → fallback
    if (!Number.isFinite(p5) || !Number.isFinite(p95) || p5 >= p95) {
      return ["auto", "auto"];
    }
    
    // sensible bounds for P/E
    const lo = Math.max(0, p5);
    const hi = Math.max(10, p95);
    
    return [Math.floor(lo), Math.ceil(hi)];
  }, [derived, clipPE]);

  return (
    <section className="bg-white dark:bg-gray-800 shadow rounded-lg p-4">
      <h3 className="text-sm font-medium mb-1">P/E (TTM)</h3>
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <LineChart
            key={`pe-${range}-${clipPE}`}
            data={data}
            syncId={syncId}
            margin={{ top: 8, right: 18, left: 8, bottom: 0 }}
          >
          <CartesianGrid strokeDasharray="3 3" />
            {/* avoid duplicate date categories when series have different date sets */}
            <XAxis dataKey="date" type="category" hide allowDuplicatedCategory={false} />
            <YAxis domain={domain} width={50} />
            <Tooltip formatter={(v) => fmtNum(Number(v))} />
            <Legend onClick={(e) => onLegend(e?.value)} onDoubleClick={(e) => onLegend(e?.value, true)} />
            {derived.map((s) => (
              <Line
                key={s.t}
                name={s.t}
                /* choose ONE: 'stepAfter' (stair steps) or 'linear' (straight segments) */
                type="linear"
                dataKey={s.t}
                stroke={colors[s.t]}
                strokeWidth={hidden[s.t] ? 1 : 2}
                opacity={hidden[s.t] ? 0.25 : 1}
                dot={{ r: 2 }}           /* show actual quarterly points */
                activeDot={{ r: 3 }}
                connectNulls              /* draw across dates where a series has no point */
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function EPSGrid({ derived, range, colors }) {
  const hasAny = derived.some((d) => d.eps.length);
  if (!hasAny) return null;

  return (
    <section className="bg-white dark:bg-gray-800 shadow rounded-lg p-4">
      <h3 className="text-sm font-medium mb-1">EPS (TTM) — per company</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {derived.map((d) => {
          // simple dynamic width: fewer points => wider bars (clamped 4..12 px)
          return (
            <div key={d.t} className="border rounded-lg p-3 dark:border-gray-700">
              <div className="text-xs mb-1" style={{ color: colors[d.t] }}>{d.t}</div>
              <div className="h-40">
                <ResponsiveContainer>
                  {/*<LineChart key={`eps-${d.t}-${range}`} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                  <XAxis dataKey="date" type="category" hide />
                  <YAxis domain={["auto", "auto"]} width={40} />
                  <Tooltip formatter={(v) => fmtNum(Number(v))} />
                  <Line type="monotone" data={d.eps} dataKey="v" stroke={colors[d.t]} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>*/}
                  <BarChart
   key={`eps-${d.t}-${range}`}
   data={d.eps}
   syncId="cmp"
   margin={{ top: 4, right: 8, left: 8, bottom: 0 }}
   barCategoryGap="15%"   // increase category spacing (visually narrower bars)
   barGap={0}             // no gap (only one series)
 >
   <XAxis dataKey="date" type="category" hide />
   <YAxis domain={["auto", "auto"]} width={40} />
   <Tooltip formatter={(v) => fmtNum(Number(v))} />
   <Bar
     dataKey="v"
     fill={colors[d.t]}
     isAnimationActive={false}
     maxBarSize={100}       // optional cap so sparse data doesn't create fat bars
   />
 </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function CompareTable({ derived, range }) {
  const rows = useMemo(() => {
    return derived.map((d) => {
      const price = d.priceIdx;
      const last = price[price.length - 1]?.v ?? null;
      const first = price[0]?.v ?? null;
      const retWindow = last != null && first != null ? (last - first) : null; // % vs window start (indexed base 100)

      function pctOver(period) {
        const idx = indexPrice(
          d.priceIdx.map((p) => ({ date: p.date, close: p.v })), // reuse indexed as "close"
          (period)
        );
        if (!idx.length) return null;
        const end = idx[idx.length - 1].v;
        return end - 100; // since base is 100
      }

      return {
        t: d.t,
	last: d.lastClose,  
        retWindow: retWindow, // matches current range (already pct-from-100)
        ret3M: pctOver("3M"),
        ret1Y: pctOver("1Y"),
        pe: d.pe.length ? d.pe[d.pe.length - 1].v : null,
        eps: d.eps.length ? d.eps[d.eps.length - 1].v : null,

        revenue_growth_1y: d.growth?.revenue_growth_1y ?? null,
        revenue_growth_3y: d.growth?.revenue_growth_3y ?? null,
        revenue_growth_5y: d.growth?.revenue_growth_5y ?? null,
        price_growth_5y: d.growth?.price_growth_5y ?? null,
      };
    });
  }, [derived, range]);

  const [sortKey, setSortKey] = useState("t");
  const [asc, setAsc] = useState(true);

  const sorted = useMemo(() => {
    const out = rows.slice();
    out.sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      if (av === bv) return 0;
      return (av < bv ? -1 : 1) * (asc ? 1 : -1);
    });
    return out;
  }, [rows, sortKey, asc]);

  function header(label, key, align = "left") {
    const active = sortKey === key;
    return (
      <th className={`px-2 py-1 text-xs font-medium ${align === "right" ? "text-right" : "text-left"}`}>
        <button className={`inline-flex items-center gap-1 ${active ? "" : "opacity-70"}`} onClick={() => { if (active) setAsc(!asc); else { setSortKey(key); setAsc(false); } }}>
          {label}
          {active ? (asc ? "▲" : "▼") : null}
        </button>
      </th>
    );
  }

  return (
    <section className="bg-white dark:bg-gray-800 shadow rounded-lg p-4">
      <h3 className="text-sm font-medium mb-1">Summary</h3>
      <div className="overflow-x-auto">
        <table className="min-w-[720px] w-full text-sm border dark:border-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              {header("Ticker", "t")}
	      {header("Last Price", "last", "right")}
              {header(`Return (${range})`, "retWindow", "right")}
              {header("Return 3M", "ret3M", "right")}
              {header("Return 1Y", "ret1Y", "right")}
              {header("P/E (TTM)", "pe", "right")}
              {header("EPS (TTM)", "eps", "right")}
              {header("Revenue Growth (1y)", "revenue_growth_1y", "right")}
              {header("Revenue Growth (3y)", "revenue_growth_3y", "right")}
              {header("Revenue Growth (5y)", "revenue_growth_5y", "right")}
              {header("Price Growth (5y)", "price_growth_5y", "right")}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
	      <tr key={r.t} className="border-t">
 <td className="px-2 py-1">
   <Link
     to={`/stock/${r.t}`}
     className="text-blue-600 dark:text-blue-400 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-sm"
     aria-label={`Open details for ${r.t}`}
   >
     {r.t}
   </Link>
 </td>
 <td className="px-2 py-1 text-right">
   {r.last == null ? "—" : `$${fmtNum(r.last)}`}
 </td>
                <td className="px-2 py-1 text-right">{r.retWindow == null ? "—" : `${r.retWindow.toFixed(1)}%`}</td>
                <td className="px-2 py-1 text-right">{r.ret3M == null ? "—" : `${r.ret3M.toFixed(1)}%`}</td>
                <td className="px-2 py-1 text-right">{r.ret1Y == null ? "—" : `${r.ret1Y.toFixed(1)}%`}</td>
                <td className="px-2 py-1 text-right">{r.pe == null ? "—" : fmtNum(r.pe)}</td>
                <td className="px-2 py-1 text-right">{r.eps == null ? "—" : fmtNum(r.eps)}</td>
                <td className="px-2 py-1 text-right">
                  {r.revenue_growth_1y != null ? r.revenue_growth_1y.toFixed(2) + "%" : "—"}
                </td>
                <td className="px-2 py-1 text-right">
                  {r.revenue_growth_3y != null ? r.revenue_growth_3y.toFixed(2) + "%" : "—"}
                </td>
                <td className="px-2 py-1 text-right">
                  {r.revenue_growth_5y != null ? r.revenue_growth_5y.toFixed(2) + "%" : "—"}
                </td>
                <td className="px-2 py-1 text-right">
                  {r.price_growth_5y != null ? r.price_growth_5y.toFixed(2) + "%" : "—"}
                </td>
	      </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
