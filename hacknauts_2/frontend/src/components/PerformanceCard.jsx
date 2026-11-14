import { motion } from "framer-motion";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const BEFORE = "hsl(var(--danger))";
const AFTER = "hsl(var(--success))";
const tip = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 10, fontSize: 12, color: "hsl(var(--foreground))" };

// Shows charts once the backend returns report.load_test = { curve: [{ users, beforeMs, afterMs, beforeErr, afterErr }] }.
export default function PerformanceCard({ report }) {
  const curve = report?.load_test?.curve;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance under load</CardTitle>
        <CardDescription>{curve ? `${report.repo_name}: before and after optimization` : "Load testing is the next phase. Charts will appear here."}</CardDescription>
      </CardHeader>
      <CardContent>
        {curve ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid gap-6 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-sm font-medium">Response time (ms)</p>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="users" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                  <Tooltip contentStyle={tip} />
                  <Legend />
                  <ReferenceLine x={curve.find((c) => c.users >= report.target_users)?.users} stroke="hsl(var(--primary))" strokeDasharray="4 4" />
                  <Line name="Before" type="monotone" dataKey="beforeMs" stroke={BEFORE} strokeWidth={2.5} dot={false} />
                  <Line name="After" type="monotone" dataKey="afterMs" stroke={AFTER} strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div>
              <p className="mb-2 text-sm font-medium">Error rate (%)</p>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="users" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                  <Tooltip contentStyle={tip} cursor={{ fill: "hsl(var(--muted))" }} />
                  <Legend />
                  <Bar name="Before" dataKey="beforeErr" fill={BEFORE} radius={[4, 4, 0, 0]} />
                  <Bar name="After" dataKey="afterErr" fill={AFTER} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        ) : (
          <div className="grid h-40 place-items-center rounded-md border border-dashed text-center text-sm text-muted-foreground">
            <p className="max-w-sm">The code analysis is live. Response time and error rate against concurrent users need the k6 load-testing step.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
