import { cn } from "@/lib/utils";

const tones = {
  default: "bg-muted text-foreground",
  success: "bg-success/15 text-success",
  danger: "bg-danger/15 text-danger",
  warn: "bg-warn/20 text-warn",
  primary: "bg-primary/15 text-primary",
};
export const Badge = ({ tone = "default", className, ...p }) => (
  <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", tones[tone], className)} {...p} />
);
