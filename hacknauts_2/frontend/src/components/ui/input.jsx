import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-10 w-full rounded-md border bg-card px-3 text-sm placeholder:text-muted-foreground disabled:opacity-50",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";
