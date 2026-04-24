"use client"

import { motion } from "framer-motion"
import { Radar, Layers, Gauge, Send } from "lucide-react"

const STEPS = [
  {
    n: "01",
    icon: Radar,
    title: "Discover",
    body: "Define a typed search job: ICP, geo, funding, tech. Run it. Get a reproducible candidate set — never a CSV export.",
  },
  {
    n: "02",
    icon: Layers,
    title: "Normalize",
    body: "Providers merge into a canonical schema. Conflicts surface for review; completeness and freshness are first-class fields.",
  },
  {
    n: "03",
    icon: Gauge,
    title: "Score",
    body: "Deterministic, weighted, explainable. Adjust a weight and every lead re-ranks in sub-second with a full audit diff.",
  },
  {
    n: "04",
    icon: Send,
    title: "Outreach",
    body: "AI drafts with inline citations. Your team approves. Sent messages are logged to the ledger. No autonomous sends.",
  },
]

export function WorkflowSection() {
  return (
    <section id="workflow" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mx-auto flex max-w-2xl flex-col items-center text-center"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
            The workflow
          </div>
          <h2 className="mt-4 text-pretty text-[36px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">
            From blank query to approved outreach in one governed pipeline.
          </h2>
        </motion.div>

        <div className="relative mt-20">
          {/* Connector */}
          <div className="pointer-events-none absolute left-0 right-0 top-[27px] hidden h-px lg:block">
            <div className="mx-auto h-full max-w-5xl bg-gradient-to-r from-transparent via-border to-transparent" />
          </div>

          <div className="grid grid-cols-1 gap-8 lg:grid-cols-4 lg:gap-6">
            {STEPS.map((s, i) => {
              const Icon = s.icon
              return (
                <motion.div
                  key={s.n}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-60px" }}
                  transition={{ delay: i * 0.12, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                  className="relative flex flex-col"
                >
                  <div className="relative mb-6 flex size-14 items-center justify-center rounded-2xl border border-border bg-card">
                    <div
                      className="absolute inset-0 rounded-2xl"
                      style={{
                        background:
                          "radial-gradient(circle at 30% 20%, oklch(0.82 0.14 195 / 0.15), transparent 60%)",
                      }}
                    />
                    <Icon className="size-5 text-[oklch(var(--signal))]" />
                  </div>
                  <div className="mb-2 font-mono text-[11px] font-medium tracking-[0.14em] text-muted-foreground">
                    STEP {s.n}
                  </div>
                  <h3 className="text-[18px] font-semibold tracking-tight text-foreground">{s.title}</h3>
                  <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{s.body}</p>
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
