"use client"

import { motion } from "framer-motion"
import { CheckCircle2, FileSearch, GitCommit, Lock } from "lucide-react"

const POINTS = [
  {
    icon: FileSearch,
    title: "Every field is sourced",
    body: "No orphaned data. Each attribute on a lead traces to a named provider, a timestamp, and a confidence score.",
  },
  {
    icon: GitCommit,
    title: "Every score is reproducible",
    body: "Scoring models are pinned to commits. Re-run any historical decision and reproduce it byte-for-byte.",
  },
  {
    icon: Lock,
    title: "Every change is immutable",
    body: "Cryptographically chained event log. Exports, edits, approvals, sends — all permanent, all provable.",
  },
]

export function EvidenceSection() {
  return (
    <section id="evidence" className="relative overflow-hidden py-24 lg:py-32">
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute left-[-10%] top-1/2 h-[500px] w-[500px] -translate-y-1/2 rounded-full blur-3xl"
          style={{
            background: "radial-gradient(circle, oklch(0.78 0.16 152 / 0.14), transparent 70%)",
          }}
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
            Evidence ledger
          </div>
          <h2 className="mt-4 text-pretty text-[36px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">
            Traceable by design.
            <br />
            Defensible by default.
          </h2>
          <p className="mt-5 max-w-xl text-pretty text-base leading-relaxed text-muted-foreground">
            Most lead platforms are black boxes. LeadScope is an evidence ledger — every signal, every
            score, every decision is citable. If you can&apos;t trace it, we don&apos;t show it.
          </p>

          <div className="mt-10 flex flex-col gap-4">
            {POINTS.map((p, i) => {
              const Icon = p.icon
              return (
                <motion.div
                  key={p.title}
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
                    <h4 className="text-[14px] font-semibold text-foreground">{p.title}</h4>
                    <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{p.body}</p>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </motion.div>

        {/* Evidence ledger visual */}
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
  )
}

const EVENTS = [
  { t: "12:04:12", src: "Clearbit", msg: "Company record hydrated", hash: "8f2a..." },
  { t: "12:04:13", src: "LinkedIn", msg: "Hiring signals synced · 15 growth roles", hash: "c1b9..." },
  { t: "12:04:13", src: "BuiltWith", msg: "Techstack fingerprinted · 38 tools", hash: "3e71..." },
  { t: "12:04:14", src: "ScoreEngine", msg: "Model v4.2.1 applied · grade A · 87", hash: "a9c4..." },
  { t: "12:04:15", src: "Reviewer", msg: "avery@ approved for outreach queue", hash: "7b20..." },
  { t: "12:04:16", src: "OutreachAI", msg: "Draft generated with 4 citations", hash: "d5f8..." },
]

function EvidenceLedger() {
  return (
    <div className="relative">
      <div
        className="absolute -inset-6 rounded-3xl opacity-40 blur-2xl"
        style={{
          background:
            "linear-gradient(135deg, oklch(0.78 0.16 152 / 0.3), oklch(0.82 0.14 195 / 0.2), transparent)",
        }}
      />

      <div className="relative overflow-hidden rounded-2xl border border-border bg-card/80 shadow-2xl backdrop-blur">
        <div className="flex items-center justify-between border-b border-border bg-background/60 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex size-6 items-center justify-center rounded-md bg-[oklch(var(--evidence)/0.15)] text-[oklch(var(--evidence))]">
              <Lock className="size-3.5" />
            </div>
            <div>
              <div className="text-[12px] font-semibold leading-tight">Lead ledger · ld_01hpn</div>
              <div className="font-mono text-[10px] leading-tight text-muted-foreground">
                chain-root: 0x8f2a…c1b9
              </div>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] px-2 py-0.5 text-[10px] font-medium text-[oklch(var(--evidence))]">
            <CheckCircle2 className="size-3" />
            Verified
          </span>
        </div>

        <div className="relative px-5 py-4">
          {/* Vertical chain line */}
          <div className="absolute bottom-4 left-[30px] top-5 w-px bg-border" />

          <div className="flex flex-col gap-3.5">
            {EVENTS.map((e, i) => (
              <motion.div
                key={e.hash}
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
                    <span className="text-[12px] font-medium text-foreground">{e.src}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">{e.t}</span>
                  </div>
                  <div className="mt-0.5 text-[12px] leading-snug text-muted-foreground">{e.msg}</div>
                  <div className="mt-1 font-mono text-[10px] text-muted-foreground/70">hash {e.hash}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
