"use client";

import { useState } from "react";
import { Search, Loader2, ShieldCheck, Zap, BarChart3 } from "lucide-react";

export default function Home() {
  const [keyword, setKeyword] = useState("");
  const [country, setCountry] = useState("US");
  const [limit, setLimit] = useState(5);
  const [isScanning, setIsScanning] = useState(false);

  const handleScan = async () => {
    if (!keyword) return;
    setIsScanning(true);
    
    // In Phase 28, this will connect to the FastAPI backend via axios
    // For now, we simulate the enterprise loading state
    setTimeout(() => {
      setIsScanning(false);
      alert("Scan initiated. Backend integration coming in Phase 28.");
    }, 2000);
  };

  return (
    <div className="flex flex-col gap-12">
      {/* Header */}
      <header className="flex flex-col gap-4 border-b border-zinc-800 pb-8">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/20 rounded-lg border border-blue-500/30">
            <ShieldCheck className="w-6 h-6 text-blue-400" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Ad-Leak-Engine</h1>
          <span className="px-2 py-0.5 text-xs font-medium bg-zinc-800 text-zinc-400 rounded-full border border-zinc-700">SEED: 2399</span>
        </div>
        <p className="text-zinc-400 text-lg max-w-2xl">
          Enterprise-grade Meta ad infrastructure auditing. Identify tracking leaks, generate platform-specific fixes, and recover lost ROAS.
        </p>
      </header>

      {/* Control Panel */}
      <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-2xl shadow-black/20">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-500" />
          Initiate Deep Audit
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-zinc-400 mb-2">Target Niche / Keyword</label>
            <input 
              type="text" 
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g., organic skincare, B2B SaaS"
              className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Country Code</label>
            <input 
              type="text" 
              value={country}
              onChange={(e) => setCountry(e.target.value.toUpperCase())}
              maxLength={2}
              className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white uppercase focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Audit Limit</label>
            <input 
              type="number" 
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value))}
              min={1}
              max={50}
              className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
            />
          </div>
        </div>

        <button 
          onClick={handleScan}
          disabled={isScanning || !keyword}
          className="w-full md:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-semibold rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-600/20 disabled:shadow-none"
        >
          {isScanning ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Deploying Stealth Swarm...
            </>
          ) : (
            <>
              <Search className="w-5 h-5" />
              Run Infrastructure Audit
            </>
          )}
        </button>
      </section>

      {/* Metrics / Status Area (Placeholder for Phase 28 Results) */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col gap-2">
          <span className="text-zinc-500 text-sm font-medium">System Status</span>
          <span className="text-2xl font-bold text-green-400 flex items-center gap-2">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
            Operational
          </span>
          <span className="text-zinc-400 text-sm">113 Tests Passing | 0 Regressions</span>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col gap-2">
          <span className="text-zinc-500 text-sm font-medium">Detection Signals</span>
          <span className="text-2xl font-bold text-white">23 Active</span>
          <span className="text-zinc-400 text-sm">L1 Strategy | L2 Tracking | L3 UX</span>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col gap-2">
          <span className="text-zinc-500 text-sm font-medium">Financial Engine</span>
          <span className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-blue-400" />
            Holy Grail
          </span>
          <span className="text-zinc-400 text-sm">OAuth-verified CPA modeling</span>
        </div>
      </section>
    </div>
  );
}
