import { LogOut, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/Auth";
import { useTheme } from "@/context/Theme";

// User info on top, theme toggle directly underneath.
export default function UserMenu() {
  const { user, signOut } = useAuth();
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";

  return (
    <div className="flex min-w-[11rem] flex-col gap-1.5 rounded-lg border bg-card px-3 py-2">
      <div className="flex items-center gap-2.5">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary/15 text-sm font-bold text-primary">
          {user.email[0].toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium leading-tight">{user.email}</p>
          <p className="text-xs text-muted-foreground">Signed in</p>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={signOut} aria-label="Sign out">
          <LogOut size={16} />
        </Button>
      </div>
      <button
        onClick={toggle}
        role="switch"
        aria-checked={dark}
        className="flex items-center justify-between rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium"
      >
        <span className="flex items-center gap-1.5">
          {dark ? <Moon size={14} /> : <Sun size={14} />}
          {dark ? "Dark theme" : "Light theme"}
        </span>
        <span className={`relative h-4 w-8 rounded-full transition-colors ${dark ? "bg-primary" : "bg-border"}`}>
          <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${dark ? "left-[18px]" : "left-0.5"}`} />
        </span>
      </button>
    </div>
  );
}
