import { Activity, Gauge } from "lucide-react";

export default function Logo({ className = "" }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <span className="grid h-9 w-9 place-items-center rounded-md bg-primary text-primary-foreground">
        <Gauge size={20} />
      </span>
      <span className="font-display text-xl font-bold tracking-tight">ScaleAI</span>
    </div>
  );
}
