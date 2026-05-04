"use client";

import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { CheckCircle2, FileSearch, GitCommit, Lock } from "lucide-react";

const ICONS = [FileSearch, GitCommit, Lock];
const EVENT_SOURCES = ["Clearbit", "LinkedIn", "BuiltWith", "ScoreEngine", "Reviewer", "OutreachAI"];
const EVENT_TIMES = ["12:04:12", "12:04:13", "12:04:13", "12:04:14", "12:04:15", "12:04:16"];
const EVENT_HASHES = ["8f2a...", "c1b9...", "3e71...", "a9c4...", "7b20...", "d5f8..."];

export function EvidenceSection() {
  const { t } = useTranslation();
  const points = t("landing.evidence.points", { returnObjects: true }) as Array<{ title: string; body: string }>;

  return (
    <section id="evidence" className="relative overflow-hidden py-24 lg:py-32">
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute left-[-10%] top-1/2 h-[500px] w-[500px] -translate-y-1/2 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, oklch(0.78 0.16 152 / 0.14), transparent 70%)" }}
        />
      </div>

      <div className="relative mx-auto grid max-w-6xl grid-cols-1 gap-16 px-6 lg:grid-cols-2 lg:gap-24">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="flex flex-col"
        >
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] px-2.5 py-0.5 text-[11px] font-medium text-[oklch(var(--evidence))]">
            {t("landing.evidence.eyebrow")}
          </div>
          <h2 className="mt-4 text-pretty text-[36px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">
            {t("landing.evidence.titleLine1")}
            <br />
            {t("landing.evidence.titleLine2")}
          </h2>
          <p className="mt-5 max-w-xl text-pretty text-base leading-relaxed text-muted-foreground">{t("landing.evidence.description")}</p>

          <div className="mt-10 flex flex-col gap-4">
            {points.map((point, i) => {
              const Icon = ICONS[i] ?? Lock;
              return (
                <motion.div
                  key={point.title}
                  initial={{ opacity: 0, x: -14 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.1 + i * 0.1, duration: 0.6 }}
                  className="flex gap-4 rounded-xl border border-border bg-card/60 p-4"
                >
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] text-[oklch(var(--evidence))]">
                    <Icon className="size-4" />
                  </div>
                  <div>
                    <h4 className="text-[14px] font-semibold text-foreground">{point.title}</h4>
                    <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{point.body}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="relative"
        >
          <EvidenceLedger />
        </motion.div>
      </div>
    </section>
  );
}

function EvidenceLedger() {
  const { t } = useTranslation();
  const events = t("landing.evidence.events", { returnObjects: true }) as string[];

  return (
    <div className="relative">
      <div
        className="absolute -inset-6 rounded-3xl opacity-40 blur-2xl"
        style={{ background: "linear-gradient(135deg, oklch(0.78 0.16 152 / 0.3), oklch(0.82 0.14 195 / 0.2), transparent)" }}
      />

      <div className="relative overflow-hidden rounded-2xl border border-border bg-card/80 shadow-2xl backdrop-blur">
        <div className="flex items-center justify-between border-b border-border bg-background/60 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex size-6 items-center justify-center rounded-md bg-[oklch(var(--evidence)/0.15)] text-[oklch(var(--evidence))]">
              <Lock className="size-3.5" />
            </div>
            <div>
              <div className="text-[12px] font-semibold leading-tight">{t("landing.evidence.ledgerTitle")}</div>
              <div className="font-mono text-[10px] leading-tight text-muted-foreground">{t("landing.evidence.ledgerRoot")}</div>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] px-2 py-0.5 text-[10px] font-medium text-[oklch(var(--evidence))]">
            <CheckCircle2 className="size-3" />
            {t("landing.evidence.verified")}
          </span>
        </div>

        <div className="relative px-5 py-4">
          <div className="absolute bottom-4 left-[30px] top-5 w-px bg-border" />
          <div className="flex flex-col gap-3.5">
            {events.map((event, i) => (
              <motion.div
                key={EVENT_HASHES[i]}
                initial={{ opacity: 0, x: 12 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 + i * 0.08 }}
                className="relative flex items-start gap-3"
              >
                <div className="relative z-10 mt-1 flex size-[18px] shrink-0 items-center justify-center rounded-full border border-[oklch(var(--evidence)/0.35)] bg-background">
                  <div className="size-1.5 rounded-full bg-[oklch(var(--evidence))]" />
                </div>
                <div className="min-w-0 flex-1 rounded-lg border border-border bg-background/60 px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[12px] font-medium text-foreground">{EVENT_SOURCES[i]}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">{EVENT_TIMES[i]}</span>
                  </div>
                  <div className="mt-0.5 text-[12px] leading-snug text-muted-foreground">{event}</div>
                  <div className="mt-1 font-mono text-[10px] text-muted-foreground/70">hash {EVENT_HASHES[i]}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
