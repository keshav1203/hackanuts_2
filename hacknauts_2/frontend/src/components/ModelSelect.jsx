import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, Cpu, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";

// Honest configuration: represents the 3-agent Groq pipeline
export const MODELS = [
  {
    id: "scaleai-groq",
    name: "ScaleAI Multi-Agent Pipeline",
    note: "Coordinated Code Analysis, Performance Testing & Optimization agents powered by Groq",
    tag: "3 Agents",
  },
];

export default function ModelSelect({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const current = MODELS.find((m) => m.id === value) || MODELS[0];

  useEffect(() => {
    const close = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    const esc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex h-10 items-center gap-2 rounded-md border bg-card px-3 text-sm font-medium hover:bg-muted"
        title="AI Agent Orchestration Architecture"
      >
        <Cpu size={16} className="text-primary" />
        <span className="hidden sm:inline">{current.name}</span>
        <ChevronDown size={16} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul
            role="listbox"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.14 }}
            className="absolute right-0 z-30 mt-2 w-80 overflow-hidden rounded-lg border bg-card p-1.5 shadow-lg"
          >
            {MODELS.map((m) => (
              <li key={m.id}>
                <button
                  role="option"
                  aria-selected={m.id === value}
                  onClick={() => {
                    onChange(m.id);
                    setOpen(false);
                  }}
                  className="flex w-full items-start gap-3 rounded-md px-3 py-2 text-left hover:bg-muted"
                >
                  <span className="mt-0.5 w-4 shrink-0">
                    {m.id === value && <Check size={16} className="text-primary" />}
                  </span>
                  <span className="flex-1">
                    <span className="flex items-center gap-2 text-sm font-medium">
                      {m.name}
                      {m.tag && <Badge tone="primary">{m.tag}</Badge>}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">{m.note}</span>
                  </span>
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
