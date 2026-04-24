"use client";

import { motion } from "framer-motion";
import { ArrowRight, PlayCircle, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { Button } from "@/components/ui/button";
import { HeroLeadCard } from "./hero-lead-card";

const CONTAINER = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
} as const;

const ITEM = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7 } },
} as const;

export function Hero() {
  return (
    <section className="relative overflow-hidden pb-24 pt-36 lg:pb-32 lg:pt-44">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-grid bg-grid-fade opacity-40" />
        <div
          className="absolute left-1/2 top-0 h-[700px] w-[1200px] -translate-x-1/2 rounded-full blur-3xl"
          style={{
            background:
              "radial-gradient(ellipse at center, oklch(0.82 0.14 195 / 0.2), transparent 60%)",
          }}
        />
        <div
          className="absolute -bottom-40 right-[-10%] h-[500px] w-[500px] rounded-full blur-3xl"
          style={{
            background: "radial-gradient(circle, oklch(0.78 0.16 152 / 0.12), transparent 70%)",
          }}
        />
      </div>

      <div className="relative mx-auto max-w-6xl px-6">
        <motion.div
          variants={CONTAINER}
          initial="hidden"
          animate="show"
          className="mx-auto flex max-w-3xl flex-col items-center text-center"
        >
          <motion.div variants={ITEM}>
            <div className="inline-flex items-center gap-2 rounded-full border border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.08)] px-3 py-1 text-[12px] font-medium text-[oklch(var(--signal))]">
              <Sparkles className="size-3.5" />
              LeadScope Intelligence 12.4 with deterministic scoring v4
            </div>
          </motion.div>

          <motion.h1
            variants={ITEM}
            className="mt-6 text-pretty text-5xl font-semibold leading-[1.04] tracking-tight sm:text-6xl lg:text-[76px]"
          >
            Evidence-first{" "}
            <span className="relative inline-block">
              <span className="relative z-10 bg-gradient-to-br from-[oklch(0.95_0.06_195)] via-[oklch(0.82_0.14_195)] to-[oklch(0.62_0.12_210)] bg-clip-text text-transparent">
                lead intelligence
              </span>
              <motion.span
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ delay: 0.9, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                className="absolute -bottom-1 left-0 h-[3px] w-full origin-left rounded-full bg-[oklch(var(--signal))]"
              />
            </span>
            <br />
            for serious operators.
          </motion.h1>

          <motion.p
            variants={ITEM}
            className="mt-6 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg"
          >
            Discover, normalize, and score B2B leads with a deterministic pipeline. Every rank
            traces to provider facts, scoring inputs, and stored evidence instead of black-box
            guesses.
          </motion.p>

          <motion.div variants={ITEM} className="mt-10 flex flex-col items-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="h-11 gap-1.5 px-5 font-medium">
              <Link to={appPaths.signUp}>
                Request access <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild variant="ghost" size="lg" className="h-11 gap-1.5 px-4 font-medium">
              <a href="#platform">
                <PlayCircle className="size-4" />
                Watch 90s product tour
              </a>
            </Button>
          </motion.div>

          <motion.div
            variants={ITEM}
            className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[12px] text-muted-foreground"
          >
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="size-3.5 text-[oklch(var(--evidence))]" />
              SOC 2 Type II
            </div>
            <div>GDPR and CCPA ready</div>
            <div>99.98% uptime SLA</div>
            <div>Used by 1,400+ agencies</div>
          </motion.div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 1, ease: [0.22, 1, 0.36, 1] }}
          className="relative mx-auto mt-20 max-w-5xl"
        >
          <HeroLeadCard />
        </motion.div>
      </div>
    </section>
  );
}
