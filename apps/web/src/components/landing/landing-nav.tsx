"use client";

import { motion, useMotionValueEvent, useScroll } from "framer-motion";
import { useState } from "react";
import { ArrowRight, Menu, X } from "lucide-react";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { LeadScopeWordmark } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { ThemeSwitcher } from "@/components/shell/theme-switcher";
import { LanguageSwitcher } from "@/components/shell/language-switcher";
import { cn } from "@/lib/utils";

const LINKS = [
  { label: "Platform", href: "#platform" },
  { label: "Evidence", href: "#evidence" },
  { label: "Workflow", href: "#workflow" },
  { label: "Pricing", href: "#pricing" },
  { label: "Docs", href: "#docs" },
];

export function LandingNav() {
  const { scrollY } = useScroll();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useMotionValueEvent(scrollY, "change", (value) => {
    setScrolled(value > 12);
  });

  return (
    <motion.header
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-4"
    >
      <div
        className={cn(
          "flex w-full max-w-6xl items-center justify-between gap-6 rounded-full border px-4 py-2.5 transition-all duration-300",
          scrolled
            ? "border-border bg-background/80 shadow-[0_8px_32px_-12px_oklch(0_0_0/0.6)] backdrop-blur-xl"
            : "border-transparent bg-transparent",
        )}
      >
        <Link to={appPaths.home} className="flex items-center gap-2">
          <LeadScopeWordmark />
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-full px-3 py-1.5 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-1 md:flex">
          <LanguageSwitcher />
          <ThemeSwitcher />
          <Button asChild variant="ghost" size="sm" className="h-8 text-[13px] font-medium">
            <Link to={appPaths.login}>Sign in</Link>
          </Button>
          <Button asChild size="sm" className="h-8 gap-1 text-[13px] font-medium">
            <Link to={appPaths.signUp}>
              Request access <ArrowRight className="size-3.5" />
            </Link>
          </Button>
        </div>

        <button
          type="button"
          className="inline-flex size-9 items-center justify-center rounded-full border border-border text-foreground md:hidden"
          onClick={() => setOpen((value) => !value)}
          aria-label="Toggle menu"
        >
          {open ? <X className="size-4" /> : <Menu className="size-4" />}
        </button>
      </div>

      {open ? (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute inset-x-4 top-[72px] flex flex-col gap-1 rounded-2xl border border-border bg-background/95 p-3 shadow-xl backdrop-blur-xl md:hidden"
        >
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="rounded-lg px-3 py-2.5 text-sm font-medium text-foreground hover:bg-accent"
            >
              {link.label}
            </a>
          ))}
          <div className="mt-2 border-t border-border pt-3">
            <div className="flex items-center justify-end gap-1 pb-2">
              <LanguageSwitcher />
              <ThemeSwitcher />
            </div>
            <div className="flex gap-2">
              <Button asChild variant="outline" size="sm" className="flex-1 bg-transparent">
                <Link to={appPaths.login}>Sign in</Link>
              </Button>
              <Button asChild size="sm" className="flex-1">
                <Link to={appPaths.signUp}>Request access</Link>
              </Button>
            </div>
          </div>
        </motion.div>
      ) : null}
    </motion.header>
  );
}
