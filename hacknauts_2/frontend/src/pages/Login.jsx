import { useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, Eye, EyeOff, Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import Logo from "@/components/Logo";
import { DEMO, useAuth } from "@/context/Auth";

export default function Login() {
  const { signIn, signUp, demoSignIn } = useAuth();
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const demo = async () => {
    setError("");
    try { await demoSignIn(); } catch (err) { setError(err.message); }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError("Enter a valid email address.");
    if (password.length < 6) return setError("Password must be at least 6 characters.");
    setBusy(true);
    try {
      await (mode === "signin" ? signIn(email, password) : signUp(email, password));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="w-full max-w-md">
        <Logo className="mb-6 justify-center" />
        <Card className="p-7 shadow-xl shadow-primary/5">
          <h1 className="text-2xl font-bold">{mode === "signin" ? "Sign in to ScalePilot" : "Create your account"}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Paste a repository, find what breaks under load, and fix it.
          </p>

          <div className="mt-5 grid grid-cols-2 rounded-md bg-muted p-1 text-sm font-medium" role="tablist">
            {[["signin", "Sign in"], ["signup", "Create account"]].map(([id, label]) => (
              <button
                key={id}
                role="tab"
                aria-selected={mode === id}
                onClick={() => { setMode(id); setError(""); }}
                className={`rounded-sm py-1.5 transition-colors ${mode === id ? "bg-card shadow-sm" : "text-muted-foreground"}`}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-5 space-y-4" noValidate>
            <div className="space-y-1.5">
              <label htmlFor="email" className="text-sm font-medium">Email</label>
              <Input id="email" type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="password" className="text-sm font-medium">Password</label>
              <div className="relative">
                <Input
                  id="password"
                  type={show ? "text" : "password"}
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  placeholder="At least 6 characters"
                  className="pr-10"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-2.5 top-2.5 text-muted-foreground">
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {error && (
              <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} role="alert" className="flex items-start gap-2 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
                <AlertCircle size={16} className="mt-0.5 shrink-0" /> {error}
              </motion.p>
            )}

            <Button type="submit" className="w-full" disabled={busy}>
              {busy && <Loader2 size={16} className="animate-spin" />}
              {mode === "signin" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
          </div>

          <Button variant="outline" className="w-full" onClick={demo}>
            <Play size={16} /> Try the demo account
          </Button>
          <p className="mt-2 text-center text-xs text-muted-foreground">{DEMO.email} / {DEMO.password}</p>
        </Card>
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Each email has one active session. Signing in somewhere else ends the previous one.
        </p>
      </motion.div>
    </main>
  );
}
