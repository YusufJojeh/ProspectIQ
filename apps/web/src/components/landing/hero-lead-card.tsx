"use client"

import { motion } from "framer-motion"
import { ArrowUpRight, CheckCircle2, Database, ExternalLink, Link2, Sparkles } from "lucide-react"

const SCORE = 87

const BREAKDOWN = [
  { label: "ICP fit", value: 92, tone: "oklch(var(--signal))" },
  { label: "Budget signal", value: 84, tone: "oklch(var(--evidence))" },
  { label: "Timing intent", value: 78, tone: "oklch(var(--caution))" },
  { label: "Data completeness", value: 96, tone: "oklch(var(--signal))" },
]

const EVIDENCE = [
  { src: "Clearbit", label: "Series B · $42M raised Mar 2026", conf: 0.98 },
  { src: "LinkedIn", label: "15 hires on Growth team in 90d", conf: 0.94 },
  { src: "BuiltWith", label: "Segment + HubSpot + Intercom", conf: 0.99 },
  { src: "Earnings call", label: "CFO: shifting CAC spend to ABM", conf: 0.82 },
]

export function HeroLeadCard() {
  return (
    <div className="relative">
      {/* Signal glow behind card */}
      <div
        className="absolute -inset-4 rounded-[28px] opacity-50 blur-2xl"
        style={{
          background:
            "linear-gradient(135deg, oklch(0.82 0.14 195 / 0.35), oklch(0.78 0.16 152 / 0.25), transparent)",
        }}
      />

      <div className="relative overflow-hidden rounded-2xl border border-border bg-card/90 shadow-[0_40px_120px_-20px_oklch(0_0_0/0.7)] backdrop-blur-xl">
        {/* Browser chrome */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-background/60 px-3 py-3 sm:px-4">
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex gap-1.5">
              <div className="size-2.5 rounded-full bg-[oklch(0.62_0.18_25)]" />
              <div className="size-2.5 rounded-full bg-[oklch(0.78_0.16_85)]" />
              <div className="size-2.5 rounded-full bg-[oklch(0.75_0.16_152)]" />
            </div>
            <div className="ml-2 flex min-w-0 items-center gap-1.5 rounded-md border border-border bg-background/80 px-2 py-1 font-mono text-[10px] text-muted-foreground">
              <Link2 className="size-3" />
              <span className="truncate">app.leadscope.io/leads/ld_01hpn</span>
            </div>
          </div>
          <div className="hidden items-center gap-1.5 text-[10px] font-medium text-muted-foreground sm:flex">
            <span className="inline-flex size-1.5 rounded-full bg-[oklch(var(--evidence))]" />
            Live pipeline · v4.2.1
          </div>
        </div>

        <div className="grid gap-0 md:grid-cols-[minmax(0,1.2fr),minmax(0,1fr)]">
          {/* Lead summary */}
          <div className="border-b border-border p-4 sm:p-6 md:border-b-0 md:border-r">
            <div className="flex items-start gap-3 sm:gap-4">
              <div className="flex size-12 shrink-0 items-center justify-center rounded-xl border border-border bg-gradient-to-br from-[oklch(0.22_0.01_240)] to-[oklch(0.18_0.01_240)] text-base font-semibold tracking-tight">
                NB
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="truncate text-lg font-semibold tracking-tight">Northbeam Analytics</h3>
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] px-1.5 py-0.5 text-[10px] font-medium text-[oklch(var(--evidence))]">
                    <CheckCircle2 className="size-2.5" />
                    Verified
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted-foreground">
                  <span>Series B SaaS · 210 employees</span>
                  <span className="text-border">·</span>
                  <span>New York, NY</span>
                  <span className="text-border">·</span>
                  <span className="font-mono">ld_01hpn3k2</span>
                </div>
              </div>

              {/* Score ring */}
              <ScoreRing score={SCORE} />
            </div>

            {/* Breakdown */}
            <div className="mt-6 grid grid-cols-2 gap-3">
              {BREAKDOWN.map((b, i) => (
                <motion.div
                  key={b.label}
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.8 + i * 0.08, duration: 0.5 }}
                  className="rounded-lg border border-border bg-background/60 p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-muted-foreground">{b.label}</span>
                    <span className="font-mono text-[11px] text-foreground">{b.value}</span>
                  </div>
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-border">
                    <motion.div
                      initial={{ width: 0 }}
                      whileInView={{ width: `${b.value}%` }}
                      viewport={{ once: true }}
                      transition={{ delay: 1 + i * 0.08, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
                      className="h-full rounded-full"
                      style={{ background: b.tone }}
                    />
                  </div>
                </motion.div>
              ))}
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <button className="inline-flex items-center gap-1 rounded-md border border-border bg-background/60 px-2.5 py-1.5 text-[11px] font-medium text-foreground transition hover:bg-accent">
                View evidence ledger
                <ArrowUpRight className="size-3" />
              </button>
              <button className="inline-flex items-center gap-1 rounded-md bg-[oklch(var(--signal)/0.15)] px-2.5 py-1.5 text-[11px] font-medium text-[oklch(var(--signal))] transition hover:bg-[oklch(var(--signal)/0.22)]">
                <Sparkles className="size-3" />
                Draft outreach
              </button>
              <button className="inline-flex items-center gap-1 rounded-md border border-border bg-background/60 px-2.5 py-1.5 text-[11px] font-medium text-foreground transition hover:bg-accent">
                Add to sequence
              </button>
            </div>
          </div>

          {/* Evidence stream */}
          <div className="flex flex-col bg-background/30">
            <div className="flex items-center justify-between border-b border-border px-3 py-3 sm:px-5">
              <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                <Database className="size-3" />
                Evidence stream
              </div>
              <span className="font-mono text-[10px] text-muted-foreground">4 sources · 0 conflicts</span>
            </div>

            <div className="flex-1 divide-y divide-border">
              {EVIDENCE.map((e, i) => (
                <motion.div
                  key={e.label}
                  initial={{ opacity: 0, x: 16 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.9 + i * 0.1, duration: 0.5 }}
                  className="px-3 py-3.5 sm:px-5"
                >
                  <div className="flex min-w-0 items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium">
                      <span className="inline-flex size-1.5 rounded-full bg-[oklch(var(--evidence))]" />
                      <span className="truncate text-foreground">{e.src}</span>
                    </div>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      conf {(e.conf * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="mt-1 break-words text-[13px] leading-relaxed text-foreground">{e.label}</div>
                </motion.div>
              ))}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border bg-background/60 px-3 py-3 text-[11px] text-muted-foreground sm:px-5">
              <span>Scoring reproducible at commit 8f2a…</span>
              <button className="inline-flex items-center gap-1 text-foreground hover:text-[oklch(var(--signal))]">
                Open audit <ExternalLink className="size-3" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ScoreRing({ score }: { score: number }) {
  const size = 68
  const stroke = 5
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="oklch(var(--border))" strokeWidth={stroke} fill="none" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="oklch(var(--signal))"
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - (c * score) / 100 }}
          transition={{ delay: 0.8, duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="font-mono text-[18px] font-semibold text-foreground">{score}</span>
        <span className="mt-0.5 text-[8px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          Grade A
        </span>
      </div>
    </div>
  )
}
