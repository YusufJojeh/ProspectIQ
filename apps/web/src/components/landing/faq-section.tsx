"use client";

import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export function FaqSection() {
  const { t } = useTranslation();
  const items = t("landing.faq.items", { returnObjects: true }) as Array<{
    q: string;
    a: string;
  }>;

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
            {t("landing.faq.eyebrow")}
          </div>
          <h2 className="mt-4 text-pretty text-[36px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">
            {t("landing.faq.title")}
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
            {items.map((item, i) => (
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
  );
}
