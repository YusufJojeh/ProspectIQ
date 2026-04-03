import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <div className="relative">
        <select
          ref={ref}
          className={cn(
            "w-full appearance-none rounded-xl border border-[color:var(--border)] bg-white px-3 py-2.5 pe-10 text-sm outline-none transition focus:border-[color:var(--accent)] focus:ring-4 focus:ring-[rgba(15,118,110,0.12)]",
            className,
          )}
          {...props}
        >
          {children}
        </select>
        <ChevronDown className="pointer-events-none absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--muted)]" />
      </div>
    );
  },
);

Select.displayName = "Select";
