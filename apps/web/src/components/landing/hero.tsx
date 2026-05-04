"use client";

import { useLayoutEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, PlayCircle, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import gsap from "gsap";
import { appPaths } from "@/app/paths";
import { Button } from "@/components/ui/button";
import { HeroLeadCard } from "./hero-lead-card";

export function Hero() {
  const { t } = useTranslation();
  const trustItems = t("landing.hero.trust", { returnObjects: true }) as string[];
  const rootRef = useRef<HTMLElement | null>(null);

  useLayoutEffect(() => {
    if (!rootRef.current) {
      return;
    }

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches) {
      return;
    }

    const context = gsap.context(() => {
      const timeline = gsap.timeline({
        defaults: { ease: "power3.out", duration: 0.75 },
      });

      timeline
        .from("[data-hero-pill]", { opacity: 0, y: 18, duration: 0.5 }, 0.12)
        .from("[data-hero-title-line]", { opacity: 0, y: 34, stagger: 0.1 }, 0.2)
        .from("[data-hero-copy]", { opacity: 0, y: 22, duration: 0.55 }, 0.45)
        .from("[data-hero-actions]", { opacity: 0, y: 18, duration: 0.5 }, 0.58)
        .from("[data-hero-trust]", { opacity: 0, y: 14, duration: 0.45 }, 0.7)
        .from("[data-hero-card]", { opacity: 0, y: 48, scale: 0.98, duration: 0.95, ease: "expo.out" }, 0.38)
        .from("[data-hero-glow]", { opacity: 0, scale: 0.86, duration: 1.2, ease: "power2.out" }, 0)
        .fromTo(
          "[data-hero-underline]",
          { scaleX: 0, transformOrigin: "left center" },
          { scaleX: 1, duration: 0.72, ease: "power2.inOut" },
          0.92,
        );
    }, rootRef);

    return () => context.revert();
  }, []);

  return (
    <section ref={rootRef} className="relative overflow-hidden pb-24 pt-36 lg:pb-32 lg:pt-44">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-grid bg-grid-fade opacity-40" />
        <div
          data-hero-glow
          className="absolute left-1/2 top-0 h-[700px] w-[1200px] -translate-x-1/2 rounded-full blur-3xl"
          style={{
            background: "radial-gradient(ellipse at center, oklch(0.82 0.14 195 / 0.2), transparent 60%)",
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
        <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
          <div data-hero-pill>
            <div className="inline-flex items-center gap-2 rounded-full border border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.08)] px-3 py-1 text-[12px] font-medium text-[oklch(var(--signal))]">
              <Sparkles className="size-3.5" />
              {t("landing.hero.pill")}
            </div>
          </div>

          <h1 className="mt-6 text-pretty text-5xl font-semibold leading-[1.04] tracking-tight sm:text-6xl lg:text-[76px]">
            <span data-hero-title-line className="block">
              {t("landing.hero.titlePrefix")}{" "}
              <span className="relative inline-block">
                <span className="relative z-10 bg-gradient-to-br from-[oklch(0.95_0.06_195)] via-[oklch(0.82_0.14_195)] to-[oklch(0.62_0.12_210)] bg-clip-text text-transparent">
                  {t("landing.hero.titleHighlight")}
                </span>
                <span
                  data-hero-underline
                  className="absolute -bottom-1 left-0 h-[3px] w-full origin-left rounded-full bg-[oklch(var(--signal))]"
                />
              </span>
            </span>
            <span data-hero-title-line className="block">
              {t("landing.hero.titleSuffix")}
            </span>
          </h1>

          <p data-hero-copy className="mt-6 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
            {t("landing.hero.description")}
          </p>

          <div data-hero-actions className="mt-10 flex flex-col items-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="h-11 gap-1.5 px-5 font-medium">
              <Link to={appPaths.signUp}>
                {t("landing.nav.requestAccess")} <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild variant="ghost" size="lg" className="h-11 gap-1.5 px-4 font-medium">
              <a href="/product-tour/index.html" target="_blank" rel="noreferrer">
                <PlayCircle className="size-4" />
                {t("landing.hero.watchTour")}
              </a>
            </Button>
          </div>

          <div data-hero-trust className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[12px] text-muted-foreground">
            {trustItems.map((item, index) =>
              index === 0 ? (
                <div key={item} className="flex items-center gap-1.5">
                  <ShieldCheck className="size-3.5 text-[oklch(var(--evidence))]" />
                  {item}
                </div>
              ) : (
                <div key={item}>{item}</div>
              ),
            )}
          </div>
        </div>

        <div data-hero-card className="relative mx-auto mt-20 max-w-5xl">
          <HeroLeadCard />
        </div>
      </div>
    </section>
  );
}
