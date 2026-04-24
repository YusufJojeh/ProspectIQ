"use client";

import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { Button } from "@/components/ui/button";

export function CtaSection() {
  return (
    <section className="relative py-16 lg:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="relative overflow-hidden rounded-3xl border border-border bg-card px-8 py-14 text-center sm:px-16 sm:py-20"
        >
          <div className="pointer-events-none absolute inset-0">
            <div
              className="absolute inset-0"
              style={{
                background:
                  "radial-gradient(ellipse at center, oklch(0.82 0.14 195 / 0.18), transparent 60%)",
              }}
            />
            <div className="absolute inset-0 bg-grid opacity-30" />
          </div>

          <div className="relative">
            <div className="inline-flex items-center gap-2 rounded-full border border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.1)] px-2.5 py-0.5 text-[11px] font-medium text-[oklch(var(--signal))]">
              <ShieldCheck className="size-3.5" />
              Onboarding in under 72 hours
            </div>

            <h2 className="mx-auto mt-6 max-w-2xl text-pretty text-[40px] font-semibold leading-[1.05] tracking-tight sm:text-[56px]">
              Stop exporting spreadsheets.
              <br />
              Start building a ledger.
            </h2>
            <p className="mx-auto mt-5 max-w-lg text-pretty text-base leading-relaxed text-muted-foreground">
              Request access and we&apos;ll provision the workspace, load your ICP, and walk you
              through the first discovery job live.
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild size="lg" className="h-11 gap-1.5 px-5 font-medium">
                <Link to={appPaths.signUp}>
                  Request access <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg" className="h-11 bg-transparent px-5 font-medium">
                <Link to={appPaths.login}>Sign in to existing workspace</Link>
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
