"use client"

import { motion } from "framer-motion"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"

const FAQ = [
  {
    q: "What makes LeadScope different from a standard enrichment tool?",
    a: "LeadScope is not an enrichment tool — it's an evidence ledger with discovery, scoring, and outreach built on top. Every attribute on a lead is sourced, timestamped, and confidence-scored. Every rank is reproducible. Standard tools give you a row; we give you a defensible decision.",
  },
  {
    q: "Do you send outreach autonomously?",
    a: "No — and we won't. LeadScope drafts outreach with inline evidence citations, but a human approves every send. Autonomous agents writing into your customers' inboxes is a deliverability and brand risk we won't ship.",
  },
  {
    q: "Can I reproduce a lead rank from last quarter?",
    a: "Yes. Scoring models are pinned to commits. Given a lead ID and a point-in-time model version, we replay the ledger and produce the identical score, byte-for-byte. Compliance teams love this.",
  },
  {
    q: "What data providers do you integrate?",
    a: "Out of the box: Clearbit, Apollo, ZoomInfo, BuiltWith, LinkedIn (sanctioned endpoints), Crunchbase, Harmonic, plus sanctioned company filings. Team plan and above support custom provider connectors.",
  },
  {
    q: "How do you handle GDPR / CCPA?",
    a: "Typed consent tracking, per-region data residency on Team and Enterprise, DPA included, right-to-erasure workflows built into the admin surface. We are SOC 2 Type II certified and publish our security documentation on request.",
  },
  {
    q: "Can we bring our own data?",
    a: "Yes. Enterprise customers can pipe a data lake (S3, Snowflake, BigQuery) into the normalization layer and score proprietary signals alongside our providers. We never re-sell or train on customer data.",
  },
]

export function FaqSection() {
  return (
    <section id="docs" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-4xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mx-auto flex max-w-2xl flex-col items-center text-center"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
            Frequently asked
          </div>
          <h2 className="mt-4 text-pretty text-[36px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">
            Questions we get from serious operators.
          </h2>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.15, duration: 0.6 }}
          className="mt-12"
        >
          <Accordion type="single" collapsible className="flex flex-col gap-2">
            {FAQ.map((item, i) => (
              <AccordionItem
                key={i}
                value={`item-${i}`}
                className="rounded-xl border border-border bg-card/60 px-5 data-[state=open]:border-[oklch(var(--signal)/0.3)]"
              >
                <AccordionTrigger className="py-5 text-left text-[15px] font-medium hover:no-underline">
                  {item.q}
                </AccordionTrigger>
                <AccordionContent className="pb-5 text-[13px] leading-relaxed text-muted-foreground">
                  {item.a}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </motion.div>
      </div>
    </section>
  )
}
