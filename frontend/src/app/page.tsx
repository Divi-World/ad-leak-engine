"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Search, Loader2, ShieldCheck, Zap, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, Copy, Mail, Check, Settings, Sun, Moon, Key, ShieldAlert } from "lucide-react";

type ScanResult = {
  page_id: string;
  page_name: string;
  platform: string;
  confidence: number;
  leak_count: number;
  estimated_recovery: string;
  evidence_mode?: string;
  platform_evidence?: string[];
  discovered_emails?: string[];
  audit_status?: string;
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
  const [jobs, setJobs] = useState<any[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [fontSize, setFontSize] = useState<'small' | 'base' | 'large'>('base');

  const [countryOpen, setCountryOpen] = useState(false);
  const COUNTRY_REGIONS = [
    { region: "North America", countries: [{ code: "US", name: "United States" }, { code: "CA", name: "Canada" }, { code: "MX", name: "Mexico" }] },
    { region: "Europe", countries: [{ code: "GB", name: "United Kingdom" }, { code: "DE", name: "Germany" }, { code: "FR", name: "France" }, { code: "IT", name: "Italy" }, { code: "ES", name: "Spain" }, { code: "NL", name: "Netherlands" }, { code: "SE", name: "Sweden" }, { code: "NO", name: "Norway" }, { code: "DK", name: "Denmark" }, { code: "FI", name: "Finland" }, { code: "PL", name: "Poland" }, { code: "IE", name: "Ireland" }, { code: "PT", name: "Portugal" }, { code: "BE", name: "Belgium" }, { code: "CH", name: "Switzerland" }, { code: "AT", name: "Austria" }, { code: "GR", name: "Greece" }, { code: "CZ", name: "Czech Republic" }, { code: "HU", name: "Hungary" }, { code: "RO", name: "Romania" }] },
    { region: "APAC", countries: [{ code: "AU", name: "Australia" }, { code: "IN", name: "India" }, { code: "JP", name: "Japan" }, { code: "PH", name: "Philippines" }, { code: "ID", name: "Indonesia" }, { code: "TH", name: "Thailand" }, { code: "VN", name: "Vietnam" }, { code: "MY", name: "Malaysia" }, { code: "SG", name: "Singapore" }, { code: "NZ", name: "New Zealand" }] },
    { region: "LATAM", countries: [{ code: "BR", name: "Brazil" }, { code: "AR", name: "Argentina" }, { code: "CL", name: "Chile" }, { code: "CO", name: "Colombia" }, { code: "PE", name: "Peru" }] },
    { region: "MEA", countries: [{ code: "ZA", name: "South Africa" }, { code: "AE", name: "United Arab Emirates" }, { code: "SA", name: "Saudi Arabia" }, { code: "EG", name: "Egypt" }, { code: "IL", name: "Israel" }, { code: "TR", name: "Turkey" }] }
  ];
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const loadJobs = async () => {
    try {
      const response = await fetch(`${apiUrl}/jobs`, { headers: { "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "dev_key_2399" } });
      const data = await response.json();
      if (data.status === "ok") setJobs(data.jobs || []);
    } catch (error) {
      console.error("History load failed:", error);
    }
  };

  useEffect(() => { loadJobs(); }, []);

  useEffect(() => {
    const st = (localStorage.getItem('ale_theme') as 'dark' | 'light') || 'dark';
    const sf = (localStorage.getItem('ale_font') as 'small' | 'base' | 'large') || 'base';
    setTheme(st); setFontSize(sf);
    if(st === 'dark') document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
    document.documentElement.style.fontSize = sf === 'small' ? '14px' : sf === 'large' ? '18px' : '16px';
  }, []);

  const applyTheme = (t: 'dark' | 'light') => {
    if(t === 'dark') document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
    localStorage.setItem('ale_theme', t);
    setTheme(t);
  };
  const applyFont = (f: 'small' | 'base' | 'large') => {
    document.documentElement.style.fontSize = f === 'small' ? '14px' : f === 'large' ? '18px' : '16px';
    localStorage.setItem('ale_font', f);
    setFontSize(f);
  };

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
    if (res.discovered_emails && res.discovered_emails.length > 0) {
      setProspectEmail(res.discovered_emails[0]);
    } else {
      setProspectEmail("");
    }
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

  const CodeBlock = ({ children }: any) => {
    const [copied, setCopied] = useState(false);
    const handleCopy = () => {
      navigator.clipboard.writeText(String(children).replace(/\n$/, ''));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };
    return (
      <div className="relative group my-3">
        <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-x-auto text-xs">
          <code className="text-emerald-300">{children}</code>
        </pre>
        <button onClick={handleCopy} className="absolute top-2 right-2 px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
          {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    );
  };

  const mdComponents: any = {
    h1: (p: any) => <h1 className="text-2xl font-bold text-zinc-900 dark:text-white mt-6 mb-3" {...p} />,
    h2: (p: any) => <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mt-6 mb-3 border-b border-zinc-200 dark:border-zinc-800 pb-2" {...p} />,
    h3: (p: any) => <h3 className="text-lg font-semibold text-blue-700 dark:text-blue-300 mt-5 mb-2" {...p} />,
    p: (p: any) => <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed my-2" {...p} />,
    li: (p: any) => <li className="text-sm text-zinc-700 dark:text-zinc-300 ml-5 list-disc my-1" {...p} />,
    pre: (p: any) => <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-x-auto my-3 text-xs" {...p} />,
    code: ({ children, className, ...props }: any) => {
      const isBlock = className !== undefined || (typeof children === 'string' && children.includes('\n'));
      if (isBlock) return <CodeBlock>{children}</CodeBlock>;
      return <code className="text-emerald-600 dark:text-emerald-300 bg-zinc-100 dark:bg-zinc-800 px-1 rounded" {...props}>{children}</code>;
    },
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
          <div className="ml-auto flex gap-2">
            <button onClick={() => window.open(`${apiUrl.replace('/api/v1','')}/api/v1/auth/meta/login`, '_blank', 'width=600,height=700')} className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all" title="Connect Meta for deep spend analysis">
              <Key className="w-3.5 h-3.5" /> Give Full Access
            </button>
            <button onClick={() => setSettingsOpen(true)} className="p-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-all" title="Preferences">
              <Settings className="w-4 h-4" />
            </button>
          </div>
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
          <div className="relative" onMouseEnter={() => setCountryOpen(true)} onMouseLeave={() => setCountryOpen(false)}>
            <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-2">Country</label>
            <input type="text" value={country} onChange={(e) => setCountry(e.target.value.toUpperCase())} maxLength={2} className="w-full bg-white dark:bg-zinc-950 border border-zinc-300 dark:border-zinc-700 rounded-lg px-4 py-2.5 text-zinc-900 dark:text-white uppercase focus:outline-none focus:ring-2 focus:ring-blue-500/50" placeholder="Type code (e.g. US)..." />
            {countryOpen && (
              <div className="absolute z-50 left-0 mt-1 w-[600px] bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl p-6 grid grid-cols-3 gap-6">
                {COUNTRY_REGIONS.map(region => (
                  <div key={region.region}>
                    <h4 className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3 border-b border-zinc-200 dark:border-zinc-800 pb-2">{region.region}</h4>
                    <div className="space-y-1">
                      {region.countries.filter(c => c.code.includes(country) || c.name.toLowerCase().includes(country.toLowerCase())).map(c => (
                        <button key={c.code} type="button" onClick={() => { setCountry(c.code); setCountryOpen(false); }} className="w-full text-left px-3 py-1.5 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-md transition-colors flex justify-between items-center group">
                          <span>{c.name}</span>
                          <span className="text-xs font-mono text-zinc-400 group-hover:text-blue-600 dark:group-hover:text-blue-400">{c.code}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
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
                      {res.platform_evidence && res.platform_evidence.length > 0 && (
                        <p className="text-xs text-emerald-500 dark:text-emerald-400 mt-0.5 font-medium">Verified by: {res.platform_evidence.slice(0, 3).join(', ')}{res.platform_evidence.length > 3 ? ` +${res.platform_evidence.length - 3} more` : ''}</p>
                      )}
                      <p className="text-xs text-zinc-500 mt-1 font-medium">Evidence: {res.evidence_mode === 'snapshot' ? 'snapshot (24h cached)' : 'live capture'}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-zinc-400 text-xs uppercase tracking-wider">Estimated Recovery</p>
                    <p className="text-2xl font-bold text-green-400">{res.estimated_recovery}</p>
                  </div>
                </div>
                {res.audit_status === "blocked" ? (
                  <div className="flex items-center gap-2 text-sm text-orange-300 bg-orange-900/20 p-3 rounded-lg border border-orange-800/50">
                    <ShieldAlert className="w-4 h-4 text-orange-500" />
                    <span><strong className="text-orange-200">Audit Blocked:</strong> Enterprise bot protection prevented deep L2/L3 telemetry capture.</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-950 p-3 rounded-lg border border-zinc-200 dark:border-zinc-800">
                    <AlertTriangle className="w-4 h-4 text-yellow-500" />
                    <span>Detected <strong className="text-zinc-900 dark:text-white">{res.leak_count}</strong> critical revenue leaks.</span>
                  </div>
                )}
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
                    <div className="flex gap-2">
                      <button onClick={() => { const blob = new Blob([teardown], { type: "text/markdown" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "teardown.md"; a.click(); URL.revokeObjectURL(url); }} className="flex-1 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs font-medium text-white transition-all">Download Teardown (.md)</button>
                      <button onClick={() => { const blob = new Blob([messageText], { type: "text/plain" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "message.txt"; a.click(); URL.revokeObjectURL(url); }} className="flex-1 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs font-medium text-white transition-all">Download Message (.txt)</button>
                    </div>
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

      {jobs.length > 0 && (
        <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 text-white">Recent Audit History</h2>
          <div className="grid gap-2">
            {jobs.slice(0, 8).map((j: any) => (
              <button key={j.job_id} onClick={() => { setResults(j.results || []); setJobId(j.job_id); setScanStatus("completed"); setIsScanning(false); }} className="text-left px-4 py-3 bg-zinc-950 border border-zinc-800 rounded-lg hover:border-blue-500/50 transition-all">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-zinc-200">{j.job_id.slice(0, 8)}… • {j.pages} page(s)</span>
                  <span className={`text-xs font-semibold ${j.status === "completed" ? "text-green-400" : j.status === "error" ? "text-red-400" : "text-yellow-400"}`}>{j.status}</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {scanStatus === "error" && (
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-center">
          <p className="text-red-400 font-semibold">{errorDetail ? `Scan ended: ${errorDetail}.` : "Scan failed. Please check backend logs or try a different keyword."}</p>
          <p className="text-zinc-400 text-sm mt-2">Tip: the niche must have active Meta ads in the selected country. Try a broader keyword or another country code.</p>
        </div>
      )}

      {settingsOpen && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={() => setSettingsOpen(false)}>
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 max-w-md w-full shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-bold text-zinc-900 dark:text-white mb-4 flex items-center gap-2"><Settings className="w-5 h-5" /> Preferences</h3>
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-2">Theme</label>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => applyTheme('light')} className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 ${theme==='light'?'bg-blue-600 text-white':'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'}`}><Sun className="w-4 h-4" /> Light</button>
                  <button onClick={() => applyTheme('dark')} className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 ${theme==='dark'?'bg-blue-600 text-white':'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'}`}><Moon className="w-4 h-4" /> Dark</button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-2">Font Size</label>
                <div className="grid grid-cols-3 gap-2">
                  <button onClick={() => applyFont('small')} className={`px-3 py-2 rounded-lg text-xs font-medium ${fontSize==='small'?'bg-blue-600 text-white':'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'}`}>Small</button>
                  <button onClick={() => applyFont('base')} className={`px-3 py-2 rounded-lg text-sm font-medium ${fontSize==='base'?'bg-blue-600 text-white':'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'}`}>Medium</button>
                  <button onClick={() => applyFont('large')} className={`px-3 py-2 rounded-lg text-base font-medium ${fontSize==='large'?'bg-blue-600 text-white':'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'}`}>Large</button>
                </div>
              </div>
            </div>
            <button onClick={() => setSettingsOpen(false)} className="mt-6 w-full px-4 py-2 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-900 dark:text-white rounded-lg text-sm font-medium">Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
