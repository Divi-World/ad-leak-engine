"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Search, Loader2, ShieldCheck, Zap, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, Copy, Mail, Check } from "lucide-react";

type ScanResult = {
  page_id: string;
  page_name: string;
  platform: string;
  confidence: number;
  leak_count: number;
  estimated_recovery: string;
};

export default function Home() {
  const [keyword, setKeyword] = useState("");
  const [country, setCountry] = useState("US");
  const [limit, setLimit] = useState(1);
  const [isScanning, setIsScanning] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [scanStatus, setScanStatus] = useState<string>("idle");
  const [results, setResults] = useState<ScanResult[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [teardown, setTeardown] = useState<string>("");
  const [messageText, setMessageText] = useState<string>("");
  const [loadingReport, setLoadingReport] = useState(false);
  const [copied, setCopied] = useState(false);
  const [prospectEmail, setProspectEmail] = useState("");
  const [sendState, setSendState] = useState<string>("idle");
  const [sendDetail, setSendDetail] = useState<string>("");
  const [errorDetail, setErrorDetail] = useState<string>("");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("Initializing stealth swarm...");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const handleScan = async () => {
    if (!keyword) return;
    setIsScanning(true);
    setScanStatus("scanning");
    setResults([]);
    setProgress(0);
    setStage("Initializing stealth swarm...");
    setExpandedId(null);

    try {
      const response = await fetch(`${apiUrl}/scan/trigger`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "dev_key_2399"
        },
        body: JSON.stringify({ keyword, country, limit }),
      });
      const data = await response.json();
      setJobId(data.job_id);
    } catch (error) {
      console.error("Scan failed:", error);
      setScanStatus("error");
      setIsScanning(false);
    }
  };

  useEffect(() => {
    if (!jobId || scanStatus === "completed" || scanStatus === "error") return;
    const poll = setInterval(async () => {
      try {
        const response = await fetch(`${apiUrl}/scan/status/${jobId}`, { headers: { "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "dev_key_2399" } });
        const data = await response.json();
        if (data.status === "completed") {
          setResults(data.results || []);
          setScanStatus("completed");
          setIsScanning(false);
          clearInterval(poll);
        } else if (data.status === "error") {
          setScanStatus("error");
          setErrorDetail(data.message || "");
          setIsScanning(false);
          clearInterval(poll);
        } else {
          setProgress(data.progress || 0);
          setStage(data.stage || "Processing...");
        }
      } catch (error) {
        console.error("Polling failed:", error);
      }
    }, 3000);
    return () => clearInterval(poll);
  }, [jobId, scanStatus, apiUrl]);

  const toggleExpand = async (res: ScanResult) => {
    if (expandedId === res.page_id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(res.page_id);
    setLoadingReport(true);
    setTeardown("");
    setMessageText("");
    try {
      const response = await fetch(`${apiUrl}/report/${jobId}/${res.page_id}`, { headers: { "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "dev_key_2399" } });
      const data = await response.json();
      if (data.status === "ok") {
        setTeardown(data.teardown);
        setMessageText(data.message);
      }
    } catch (error) {
      console.error("Report fetch failed:", error);
    } finally {
      setLoadingReport(false);
    }
  };

  const copyMessage = async () => {
    await navigator.clipboard.writeText(messageText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const sendEmail = async (res: ScanResult) => {
    if (!prospectEmail) return;
    setSendState("sending");
    try {
      const response = await fetch(`${apiUrl}/outreach/send`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "dev_key_2399"
        },
        body: JSON.stringify({
          email: prospectEmail,
          subject: `Found ${res.leak_count} revenue leaks in ${res.page_name} ads`,
          message_text: messageText,
        }),
      });
      const data = await response.json();
      if (data.status === "success") {
        setSendState("sent");
        setSendDetail("Outreach email dispatched.");
      } else {
        setSendState("failed");
        setSendDetail(data.detail || "Send failed.");
      }
    } catch (error) {
      setSendState("failed");
      setSendDetail("Network error while sending.");
    }
  };

  const mdComponents: any = {
    h1: (p: any) => <h1 className="text-2xl font-bold text-white mt-6 mb-3" {...p} />,
    h2: (p: any) => <h2 className="text-xl font-semibold text-white mt-6 mb-3 border-b border-zinc-800 pb-2" {...p} />,
    h3: (p: any) => <h3 className="text-lg font-semibold text-blue-300 mt-5 mb-2" {...p} />,
    p: (p: any) => <p className="text-sm text-zinc-300 leading-relaxed my-2" {...p} />,
    li: (p: any) => <li className="text-sm text-zinc-300 ml-5 list-disc my-1" {...p} />,
    pre: (p: any) => <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-x-auto my-3 text-xs" {...p} />,
    code: (p: any) => <code className="text-emerald-300" {...p} />,
  };

  return (
    <div className="flex flex-col gap-12">
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

      <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-2xl shadow-black/20">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-500" />
          Initiate Deep Audit
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-zinc-400 mb-2">Target Niche / Keyword</label>
            <input type="text" value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="e.g., organic skincare" className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Country</label>
            <input type="text" value={country} onChange={(e) => setCountry(e.target.value.toUpperCase())} maxLength={2} className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white uppercase focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Limit</label>
            <input type="number" value={limit} onChange={(e) => { const v = parseInt(e.target.value, 10); setLimit(Number.isNaN(v) ? 1 : v); }} min={1} max={5} className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
          </div>
        </div>
        <button onClick={handleScan} disabled={isScanning || !keyword} className="w-full md:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-semibold rounded-lg flex items-center justify-center gap-2 transition-all">
          {isScanning ? <><Loader2 className="w-5 h-5 animate-spin" /> Deploying Stealth Swarm...</> : <><Search className="w-5 h-5" /> Run Infrastructure Audit</>}
        </button>
      </section>

      {scanStatus === "scanning" && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white">Analyzing Infrastructure... {progress}%</h3>
          <div className="w-full max-w-md mx-auto h-2 bg-zinc-800 rounded-full overflow-hidden mt-4">
            <div className="h-full bg-blue-500 transition-all duration-700" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-zinc-400 mt-3 text-sm font-medium">{stage}</p>
        </div>
      )}

      {scanStatus === "completed" && results.length > 0 && (
        <div className="grid gap-6">
          <h3 className="text-2xl font-bold text-white flex items-center gap-2"><CheckCircle className="w-6 h-6 text-green-500" /> Audit Complete — click a card to inspect the full teardown</h3>
          {results.map((res) => (
            <div key={res.page_id} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden hover:border-blue-500/50 transition-all">
              <button onClick={() => toggleExpand(res)} className="w-full text-left p-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                  <div className="flex items-center gap-3">
                    {expandedId === res.page_id ? <ChevronUp className="w-5 h-5 text-blue-400" /> : <ChevronDown className="w-5 h-5 text-zinc-500" />}
                    <div>
                      <h4 className="text-xl font-bold text-white">{res.page_name}</h4>
                      <p className="text-zinc-400 text-sm capitalize">Platform: {res.platform} (Confidence: {(res.confidence * 100).toFixed(0)}%)</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-zinc-400 text-xs uppercase tracking-wider">Estimated Recovery</p>
                    <p className="text-2xl font-bold text-green-400">{res.estimated_recovery}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-sm text-zinc-300 bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                  <AlertTriangle className="w-4 h-4 text-yellow-500" />
                  <span>Detected <strong className="text-white">{res.leak_count}</strong> critical revenue leaks.</span>
                </div>
              </button>

              {expandedId === res.page_id && (
                <div className="border-t border-zinc-800 bg-zinc-950/60 p-6 grid gap-8 lg:grid-cols-2">
                  <div>
                    <h5 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">Full Teardown Report</h5>
                    {loadingReport ? (
                      <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                    ) : (
                      <div className="max-h-[32rem] overflow-y-auto pr-2">
                        <ReactMarkdown components={mdComponents}>{teardown}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                      <h5 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Outreach Message</h5>
                      <button onClick={copyMessage} className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs font-medium text-white transition-all">
                        {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                        {copied ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 text-xs text-zinc-300 whitespace-pre-wrap max-h-64 overflow-y-auto">{messageText}</pre>
                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                      <h5 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2"><Mail className="w-4 h-4" /> Dispatch Outreach</h5>
                      <input type="email" value={prospectEmail} onChange={(e) => setProspectEmail(e.target.value)} placeholder="prospect@company.com" className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
                      <button onClick={() => sendEmail(res)} disabled={!/\S+@\S+\.\S+/.test(prospectEmail) || sendState === "sending"} className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-sm font-semibold rounded-lg transition-all">
                        {sendState === "sending" ? "Sending..." : "Send Outreach Email"}
                      </button>
                      {sendState === "failed" && <p className="text-red-400 text-xs mt-2">{sendDetail}</p>}
                      {sendState === "sent" && <p className="text-green-400 text-xs mt-2">{sendDetail}</p>}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {scanStatus === "error" && (
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-center">
          <p className="text-red-400 font-semibold">{errorDetail ? `Scan ended: ${errorDetail}.` : "Scan failed. Please check backend logs or try a different keyword."}</p>
          <p className="text-zinc-400 text-sm mt-2">Tip: the niche must have active Meta ads in the selected country. Try a broader keyword or another country code.</p>
        </div>
      )}
    </div>
  );
}
