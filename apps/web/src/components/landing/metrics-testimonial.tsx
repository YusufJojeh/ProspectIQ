"use client"

import { motion } from "framer-motion"
import { Quote } from "lucide-react"

const METRICS = [
  { value: "3.2×", label: "reply-rate lift vs. baseline outreach" },
  { value: "87%", label: "reduction in unqualified meetings" },
  { value: "12s", label: "median discovery-job completion" },
  { value: "99.98%", label: "platform uptime, measured" },
]

export function MetricsTestimonial() {
  return (
    <section className="relative border-y border-border bg-card/40 py-24 lg:py-32">
      <div className="pointer-events-none absolute inset-0 bg-dot opacity-30" />

      <div className="relative mx-auto max-w-6xl px-6">
        <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
          {METRICS.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1, duration: 0.6 }}
              className="flex flex-col gap-2"
            >
              <div className="bg-gradient-to-br from-[oklch(0.97_0.005_240)] to-[oklch(0.68_0.01_240)] bg-clip-text text-[44px] font-semibold leading-none tracking-tight text-transparent sm:text-[56px]">
                {m.value}
              </div>
              <div className="text-[13px] leading-relaxed text-muted-foreground">{m.label}</div>
            </motion.div>
          ))}
        </div>

        <motion.figure
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3, duration: 0.6 }}
          className="mt-20 grid grid-cols-1 gap-10 rounded-2xl border border-border bg-background/60 p-8 backdrop-blur md:grid-cols-[auto,minmax(0,1fr)] md:p-12"
        >
          <div className="flex flex-col items-start gap-4">
            <Quote className="size-8 text-[oklch(var(--signal))]" />
            <div className="flex items-center gap-3">
              <div className="flex size-14 items-center justify-center rounded-xl border border-border bg-gradient-to-br from-[oklch(0.22_0.01_240)] to-[oklch(0.18_0.01_240)] text-base font-semibold">
                MR
              </div>
              <div>
                <div className="text-[14px] font-semibold text-foreground">Maya Rostov</div>
                <div className="text-[12px] text-muted-foreground">VP Growth, Brightwave</div>
              </div>
            </div>
          </div>

          <blockquote className="text-pretty text-xl font-medium leading-[1.4] tracking-tight text-foreground sm:text-2xl">
            &ldquo;LeadScope is the first tool we&apos;ve used where every lead rank comes with a
            receipt. My team stopped arguing with sales about prioritization the week we rolled it
            out. The evidence ledger is genuinely unique.&rdquo;
          </blockquote>
        </motion.figure>
      </div>
    </section>
  )
}
