"use client"

import { motion } from "framer-motion"

const LOGOS = [
  "Northbeam",
  "Fathom",
  "Sequoia Labs",
  "Brightwave",
  "Parallax",
  "Meridian",
  "Helix Group",
  "Apex Signals",
]

export function LogoCloud() {
  return (
    <section className="relative border-y border-border bg-background/40">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground"
        >
          Operator teams at 1,400+ agencies run discovery on LeadScope
        </motion.p>

        <div className="mt-8 grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-4 lg:grid-cols-8">
          {LOGOS.map((name, i) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 0.7, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05, duration: 0.5 }}
              className="flex items-center justify-center text-center"
            >
              <span className="font-mono text-[13px] font-medium tracking-tight text-muted-foreground">
                {name}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
