import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          "w-full rounded-xl border border-[color:var(--border)] bg-white px-3 py-2.5 text-sm outline-none transition placeholder:text-slate-400 focus:border-[color:var(--accent)] focus:ring-4 focus:ring-[rgba(15,118,110,0.12)]",
          className,
        )}
        {...props}
      />
    );
  },
);

Input.displayName = "Input";

