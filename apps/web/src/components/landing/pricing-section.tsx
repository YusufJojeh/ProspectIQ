"use client";

import { motion } from "framer-motion";
import { ArrowRight, Check } from "lucide-react";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const TIERS = [
  {
    name: "Operator",
    price: "$480",
    suffix: "/seat / mo",
    description: "For founder-led operators running discovery end-to-end.",
    features: [
      "5,000 enriched leads / month",
      "3 scoring models",
      "Deterministic re-scoring",
      "Standard evidence ledger",
      "Email and LinkedIn draft queue",
      "SOC 2 Type II",
    ],
    cta: "Start with Operator",
    featured: false,
  },
  {
    name: "Team",
    price: "$1,850",
    suffix: "/seat / mo",
    description: "For growth teams that need approvals, governance, and a shared audit trail.",
    features: [
      "50,000 enriched leads / month",
      "Unlimited scoring models",
      "Approval workflows and RBAC",
      "Immutable evidence ledger",
      "Export retention policies",
      "SSO and SCIM provisioning",
      "Custom provider connectors",
      "Priority support and SLA",
    ],
    cta: "Talk to sales",
    featured: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    suffix: "",
    description: "For agencies with procurement, security review, and custom data residency.",
    features: [
      "Unlimited seats and usage",
      "Dedicated deployment region",
      "Bring-your-own data lake",
      "Private model hosting",
      "Named security engineer",
      "Custom DPA and MSA",
    ],
    cta: "Request proposal",
    featured: false,
  },
];

export function PricingSection() {
  return (
    <section id="pricing" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mx-auto flex max-w-2xl flex-col items-center text-center"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
            Pricing
          </div>
          <h2 className="mt-4 text-pretty text-[36px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">
            Priced per seat for teams that take discovery seriously.
          </h2>
          <p className="mt-4 text-pretty text-base leading-relaxed text-muted-foreground">
            Annual billing with usage-based enrichment. Every plan includes the evidence ledger and
            deterministic scoring engine.
          </p>
        </motion.div>

        <div className="mt-16 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {TIERS.map((tier, index) => (
            <motion.div
              key={tier.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ delay: index * 0.1, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className={cn(
                "relative flex flex-col rounded-2xl border p-6",
                tier.featured
                  ? "border-[oklch(var(--signal)/0.4)] bg-card/90 shadow-[0_30px_80px_-20px_oklch(0.82_0.14_195/0.25)]"
                  : "border-border bg-card/60",
              )}
            >
              {tier.featured ? (
                <div className="absolute -top-3 left-6 inline-flex items-center rounded-full border border-[oklch(var(--signal)/0.4)] bg-[oklch(var(--signal)/0.12)] px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-[oklch(var(--signal))]">
                  Most chosen
                </div>
              ) : null}

              <div>
                <h3 className="text-[16px] font-semibold tracking-tight text-foreground">{tier.name}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{tier.description}</p>
              </div>

              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-[40px] font-semibold tracking-tight text-foreground">{tier.price}</span>
                <span className="text-[13px] text-muted-foreground">{tier.suffix}</span>
              </div>

              <Button
                asChild
                className={cn("mt-6 h-10 font-medium", tier.featured ? "" : "bg-muted text-foreground hover:bg-accent")}
                variant={tier.featured ? "default" : "outline"}
              >
                <Link to={appPaths.signUp}>
                  {tier.cta}
                  <ArrowRight className="size-4" />
                </Link>
              </Button>

              <ul className="mt-6 flex flex-col gap-2.5 border-t border-border pt-6 text-[13px]">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 leading-relaxed text-muted-foreground">
                    <Check className="mt-0.5 size-3.5 shrink-0 text-[oklch(var(--evidence))]" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
