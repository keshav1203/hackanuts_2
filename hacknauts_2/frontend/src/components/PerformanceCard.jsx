import { useState } from "react";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Cpu, HardDrive, Layers, Zap } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Distinct color palettes per graph
const COLORS = {
  latency: {
    before: "#8b5cf6", // Purple / Violet
    after: "#06b6d4",  // Cyan / Sky Blue
  },
  errors: {
    before: "#f43f5e", // Crimson / Rose
    after: "#10b981",  // Emerald / Mint
  },
  cpu: {
    before: "#f59e0b", // Warm Amber
    after: "#14b8a6",  // Teal / Jade
  },
  memory: {
    before: "#d946ef", // Fuchsia / Magenta
    after: "#3b82f6",  // Royal Blue
  },
};

const tip = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 10,
  fontSize: 12,
  color: "hsl(var(--foreground))",
  boxShadow: "0 8px 24px -4px rgba(0,0,0,0.2)",
};

export default function PerformanceCard({ report }) {
  const [activeTab, setActiveTab] = useState("all"); // "all" | "resources" | "latency"
  const rawCurve = report?.load_test?.curve;
  const targetUsers = report?.target_users || 100;

  // Use empirical telemetry curves discovered via load testing
  const curve = rawCurve?.map((c) => ({
    ...c,
    beforeCpu: c.beforeCpu ?? 0,
    afterCpu: c.afterCpu ?? 0,
    beforeMem: c.beforeMem ?? 0,
    afterMem: c.afterMem ?? 0,
  }));

  // Calculate peak efficiency summary
  const lastPoint = curve && curve.length > 0 ? curve[curve.length - 1] : null;
  const cpuReduction = lastPoint
    ? Math.round(((lastPoint.beforeCpu - lastPoint.afterCpu) / lastPoint.beforeCpu) * 100)
    : 0;
  const memReduction = lastPoint
    ? Math.round(((lastPoint.beforeMem - lastPoint.afterMem) / lastPoint.beforeMem) * 100)
    : 0;
  const latencyReduction = lastPoint
    ? Math.round(((lastPoint.beforeMs - lastPoint.afterMs) / lastPoint.beforeMs) * 100)
    : 0;
  const errorReduction = lastPoint && lastPoint.beforeErr > 0
    ? Math.round(((lastPoint.beforeErr - lastPoint.afterErr) / lastPoint.beforeErr) * 100)
    : 0;

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Zap size={20} className="text-primary" />
            Performance & Resource Utilization under Load
          </CardTitle>
          <CardDescription>
            {curve
              ? `${report.repo_name}: multi-dimensional telemetry before vs. after optimization across virtual users`
              : "Execute the k6 load test step to generate telemetry curves."}
          </CardDescription>
        </div>

        {curve && (
          <div className="flex rounded-lg border bg-muted/40 p-0.5 text-xs font-medium">
            <button
              onClick={() => setActiveTab("all")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-all ${
                activeTab === "all"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Layers size={13} /> All 4 Plots
            </button>
            <button
              onClick={() => setActiveTab("resources")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-all ${
                activeTab === "resources"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Cpu size={13} /> CPU & Memory
            </button>
            <button
              onClick={() => setActiveTab("latency")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-all ${
                activeTab === "latency"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Activity size={13} /> Latency & Errors
            </button>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-6">
        {curve ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
            {/* Efficiency summary stat pills with corresponding graph colors */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="flex items-center gap-3 rounded-lg border bg-card/60 p-3">
                <div className="rounded-md bg-cyan-500/10 p-2 text-cyan-500">
                  <Zap size={18} />
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Latency (Line)</div>
                  <div className="text-base font-bold text-cyan-500">-{latencyReduction}% Drop</div>
                </div>
              </div>

              <div className="flex items-center gap-3 rounded-lg border bg-card/60 p-3">
                <div className="rounded-md bg-emerald-500/10 p-2 text-emerald-500">
                  <Activity size={18} />
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Error Rate (Bar)</div>
                  <div className="text-base font-bold text-emerald-500">-{errorReduction}% Lower</div>
                </div>
              </div>

              <div className="flex items-center gap-3 rounded-lg border bg-card/60 p-3">
                <div className="rounded-md bg-amber-500/10 p-2 text-amber-500">
                  <Cpu size={18} />
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Peak CPU (Area)</div>
                  <div className="text-base font-bold text-amber-500">-{cpuReduction}% Load</div>
                </div>
              </div>

              <div className="flex items-center gap-3 rounded-lg border bg-card/60 p-3">
                <div className="rounded-md bg-blue-500/10 p-2 text-blue-500">
                  <HardDrive size={18} />
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Memory (Composed)</div>
                  <div className="text-base font-bold text-blue-500">-{memReduction}% Lighter</div>
                </div>
              </div>
            </div>

            {/* Visualizations Grid: 4 Different Chart Types + 4 Different Color Palettes */}
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Plot 1: SMOOTH MULTI-LINE CHART (Indigo & Cyan) */}
              {(activeTab === "all" || activeTab === "latency") && (
                <div className="rounded-xl border bg-card/50 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold flex items-center gap-2">
                        <Zap size={15} className="text-cyan-500" /> Response Time vs. Virtual Users
                      </p>
                      <p className="text-[11px] text-muted-foreground">Line Chart • Latency reduction curve</p>
                    </div>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">Target: {targetUsers} VUs</span>
                  </div>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={curve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="users" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                      <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" unit="ms" />
                      <Tooltip contentStyle={tip} formatter={(val) => [`${val} ms`, undefined]} />
                      <Legend />
                      <ReferenceLine
                        x={curve.find((c) => c.users >= targetUsers)?.users}
                        stroke={COLORS.latency.after}
                        strokeDasharray="4 4"
                        label={{ value: "Target", fill: COLORS.latency.after, fontSize: 10 }}
                      />
                      <Line
                        name="Before (ms)"
                        type="monotone"
                        dataKey="beforeMs"
                        stroke={COLORS.latency.before}
                        strokeWidth={2.5}
                        dot={{ r: 3, fill: COLORS.latency.before }}
                      />
                      <Line
                        name="After (ms)"
                        type="monotone"
                        dataKey="afterMs"
                        stroke={COLORS.latency.after}
                        strokeWidth={2.5}
                        dot={{ r: 4, fill: COLORS.latency.after }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Plot 2: GROUPED COLUMN BAR CHART (Crimson & Emerald) */}
              {(activeTab === "all" || activeTab === "latency") && (
                <div className="rounded-xl border bg-card/50 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold flex items-center gap-2">
                        <Activity size={15} className="text-rose-500" /> Error Rate (%) vs. Virtual Users
                      </p>
                      <p className="text-[11px] text-muted-foreground">Bar Chart • Concurrency failure rate</p>
                    </div>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">Tolerance: &lt; 5%</span>
                  </div>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={curve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="users" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                      <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" unit="%" />
                      <Tooltip contentStyle={tip} cursor={{ fill: "hsl(var(--muted))" }} formatter={(val) => [`${val}%`, undefined]} />
                      <Legend />
                      <Bar
                        name="Before (%)"
                        dataKey="beforeErr"
                        fill={COLORS.errors.before}
                        radius={[6, 6, 0, 0]}
                      />
                      <Bar
                        name="After (%)"
                        dataKey="afterErr"
                        fill={COLORS.errors.after}
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Plot 3: GRADIENT AREA CHART (Warm Amber & Jade Teal) */}
              {(activeTab === "all" || activeTab === "resources") && (
                <div className="rounded-xl border bg-card/50 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold flex items-center gap-2">
                        <Cpu size={15} className="text-amber-500" /> CPU Utilization (%) vs. Virtual Users
                      </p>
                      <p className="text-[11px] text-muted-foreground">Area Chart • Processor load & headroom</p>
                    </div>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">Warning: 80%</span>
                  </div>
                  <ResponsiveContainer width="100%" height={240}>
                    <AreaChart data={curve}>
                      <defs>
                        <linearGradient id="cpuBeforeGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={COLORS.cpu.before} stopOpacity={0.5} />
                          <stop offset="95%" stopColor={COLORS.cpu.before} stopOpacity={0.02} />
                        </linearGradient>
                        <linearGradient id="cpuAfterGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={COLORS.cpu.after} stopOpacity={0.5} />
                          <stop offset="95%" stopColor={COLORS.cpu.after} stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="users" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                      <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" unit="%" domain={[0, 100]} />
                      <Tooltip contentStyle={tip} formatter={(val) => [`${val}%`, undefined]} />
                      <Legend />
                      <ReferenceLine
                        y={80}
                        stroke="#ef4444"
                        strokeDasharray="4 4"
                        label={{ value: "80% Warning", fill: "#ef4444", fontSize: 10 }}
                      />
                      <Area
                        name="Before CPU (%)"
                        type="monotone"
                        dataKey="beforeCpu"
                        stroke={COLORS.cpu.before}
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#cpuBeforeGrad)"
                      />
                      <Area
                        name="After CPU (%)"
                        type="monotone"
                        dataKey="afterCpu"
                        stroke={COLORS.cpu.after}
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#cpuAfterGrad)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Plot 4: COMPOSED BAR + LINE CHART (Fuchsia & Royal Blue) */}
              {(activeTab === "all" || activeTab === "resources") && (
                <div className="rounded-xl border bg-card/50 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold flex items-center gap-2">
                        <HardDrive size={15} className="text-blue-500" /> Memory Utilization (MB) vs. Virtual Users
                      </p>
                      <p className="text-[11px] text-muted-foreground">Composed Chart • Bar (Before) + Line (After)</p>
                    </div>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">RAM Footprint</span>
                  </div>
                  <ResponsiveContainer width="100%" height={240}>
                    <ComposedChart data={curve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="users" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                      <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" unit=" MB" />
                      <Tooltip contentStyle={tip} formatter={(val) => [`${val} MB`, undefined]} />
                      <Legend />
                      <Bar
                        name="Before RAM (MB)"
                        dataKey="beforeMem"
                        fill={COLORS.memory.before}
                        fillOpacity={0.65}
                        radius={[4, 4, 0, 0]}
                        barSize={26}
                      />
                      <Line
                        name="After RAM (MB)"
                        type="monotone"
                        dataKey="afterMem"
                        stroke={COLORS.memory.after}
                        strokeWidth={3}
                        dot={{ r: 4, fill: COLORS.memory.after, strokeWidth: 2, stroke: "#ffffff" }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </motion.div>
        ) : (
          <div className="grid h-44 place-items-center rounded-md border border-dashed text-center text-sm text-muted-foreground">
            <div className="max-w-sm space-y-1">
              <p className="font-medium text-foreground">Load test telemetry required</p>
              <p className="text-xs">
                Response time, error rate, CPU, and memory curves will appear here once the k6 load test is executed.
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
