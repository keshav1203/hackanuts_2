import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, AlertCircle, CheckCircle2, Code2, Database, FileSearch, Github, Info, Loader2, Rocket, Server, Users, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import Logo from "@/components/Logo";
import ModelSelect, { MODELS } from "@/components/ModelSelect";
import UserMenu from "@/components/UserMenu";
import QuerySection from "@/components/QuerySection";
import PerformanceCard from "@/components/PerformanceCard";
import { ArchitectureInfo, ReportView } from "@/components/ReportView";
import { api } from "@/lib/api";
import { GITHUB_RE, STEPS } from "@/lib/stages";

export default function Dashboard() {
  const [model, setModel] = useState(MODELS[0].id);
  const [url, setUrl] = useState("");
  const [target, setTarget] = useState(1000);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const timer = useRef(null);

  const running = report && (report.status === "queued" || report.status === "running");
  const finished = report && (report.status === "done" || report.status === "failed");
  const step = running ? STEPS.indexOf(report.stage) : -1;

  useEffect(() => {
    let mounted = true;
    api
      .listAnalyses()
      .then((list) => {
        if (!mounted || !list || list.length === 0) return;
        const latest = list[0];
        if (latest) {
          track(latest.id);
        }
      })
      .catch(() => {});
    return () => {
      mounted = false;
      clearTimeout(timer.current);
    };
  }, []);

  const track = (id) => {
    const tick = async () => {
      try {
        const r = await api.getAnalysis(id);
        setReport(r);
        if (r.status === "queued" || r.status === "running") timer.current = setTimeout(tick, 2000);
      } catch (e) {
        if (e.status !== 401) setError(e.message);
      }
    };
    tick();
  };

  const analyze = async (e) => {
    e.preventDefault();
    setError("");
    if (!GITHUB_RE.test(url.trim())) return setError("Paste a GitHub repository link, like https://github.com/owner/repo.");
    if (!(target > 0)) return setError("Enter how many concurrent users you need to support.");
    try {
      const r = await api.createAnalysis(url.trim(), Number(target), model);
      setReport(r);
      track(r.id);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-start justify-between gap-4 px-4 py-3 sm:px-6">
          <Logo className="mt-1" />
          <div className="flex items-start gap-3">
            <ModelSelect value={model} onChange={setModel} />
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6">
        <Card className="p-1">
          <form onSubmit={analyze}>
            <CardHeader>
              <CardTitle className="text-2xl">Find out how many users your app can really handle</CardTitle>
              <CardDescription>Paste a public repository and your target traffic. ScaleAI's 3 specialized agents inspect the code, formulate test plans, and suggest optimizations.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-col gap-3 md:flex-row">
                <div className="relative flex-1">
                  <Github size={18} className="absolute left-3 top-3 text-muted-foreground" />
                  <Input aria-label="Repository link" className="pl-10" placeholder="https://github.com/owner/repo" value={url} onChange={(e) => setUrl(e.target.value)} disabled={running} />
                </div>
                <div className="relative md:w-56">
                  <Users size={18} className="absolute left-3 top-3 text-muted-foreground" />
                  <Input aria-label="Target concurrent users" type="number" min="1" className="pl-10" value={target} onChange={(e) => setTarget(e.target.value)} disabled={running} />
                </div>
                <Button type="submit" disabled={running} className="md:w-40">
                  {running ? <Loader2 size={16} className="animate-spin" /> : <Rocket size={16} />}
                  {running ? "Analyzing" : "Analyze"}
                </Button>
              </div>
              {error && <p role="alert" className="flex items-center gap-2 text-sm text-danger"><AlertCircle size={16} />{error}</p>}

              <AnimatePresence>
                {running && (
                  <motion.ol initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="flex flex-wrap gap-2 overflow-hidden pt-1">
                    {STEPS.map((s, i) => (
                      <li key={s} className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${i < step ? "bg-success/15 text-success" : i === step ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>
                        {i < step ? <CheckCircle2 size={14} /> : i === step ? <Loader2 size={14} className="animate-spin" /> : null}
                        {s}
                      </li>
                    ))}
                  </motion.ol>
                )}
              </AnimatePresence>
            </CardContent>
          </form>
        </Card>

        <div className="grid gap-5 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><FileSearch size={18} className="text-primary" /> ScaleAI Multi-Agent Report</CardTitle>
              <CardDescription>{finished && report.status === "done" ? report.repo_name : "Findings, load tests and suggested fixes appear here."}</CardDescription>
            </CardHeader>
            <CardContent>
              {finished ? (
                <ReportView report={report} onUpdate={(updated) => setReport(updated)} />
              ) : (
                <div className="grid h-48 place-items-center rounded-md border border-dashed text-center text-sm text-muted-foreground">
                  <p className="max-w-xs">{running ? `${report.stage}. Multi-agent analysis in progress.` : "Paste a repository above and press Analyze to see scalability issues, why they matter, and how to fix them."}</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Info size={18} className="text-primary" /> Architecture & Telemetry</CardTitle>
              <CardDescription>{report?.status === "done" ? "What ScaleAI detected." : "Stack and architecture show here."}</CardDescription>
            </CardHeader>
            <CardContent>
              {report?.status === "done" ? (
                <ArchitectureInfo report={report} />
              ) : (
                <ul className="space-y-3 text-sm text-muted-foreground">
                  {[[Code2, "Agent 1: In-depth code quality, N+1 queries, blocking calls"], [Activity, "Agent 2: Endpoint discovery, k6 scenario scripting, latency bounds"], [Zap, "Agent 3: Root-cause synthesis, minimal patches & validation"]].map(([I, t]) => (
                    <li key={t} className="flex gap-3"><I size={18} className="mt-0.5 shrink-0 text-primary" />{t}</li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <PerformanceCard report={report} />
        <QuerySection
          reportId={report?.status === "done" ? report.id : undefined}
          repo={report?.status === "done" ? report.repo_name : undefined}
          model={MODELS.find((m) => m.id === model)?.name || "ScaleAI Multi-Agent Pipeline"}
        />
      </main>
    </div>
  );
}
