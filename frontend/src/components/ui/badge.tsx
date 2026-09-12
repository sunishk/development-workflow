import * as React from "react";
import { cn } from "@/lib/utils";

const variants: Record<string, string> = {
  default: "bg-primary text-primary-foreground",
  outline: "border border-border bg-card text-foreground",
  queued: "border border-sky-200 bg-sky-50 text-sky-800",
  success: "border border-emerald-200 bg-emerald-50 text-emerald-800",
  failed: "border border-red-200 bg-red-50 text-red-800",
  local: "border border-violet-200 bg-violet-50 text-violet-800",
};

export function Badge({
  className,
  variant = "default",
  children,
}: {
  className?: string;
  variant?: keyof typeof variants;
  children: React.ReactNode;
}) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium", variants[variant], className)}>
      {children}
    </span>
  );
}
