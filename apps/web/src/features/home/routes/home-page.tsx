import { CtaSection } from "@/components/landing/cta-section";
import { EvidenceSection } from "@/components/landing/evidence-section";
import { FaqSection } from "@/components/landing/faq-section";
import { FeaturesBento } from "@/components/landing/features-bento";
import { Hero } from "@/components/landing/hero";
import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingNav } from "@/components/landing/landing-nav";
import { LogoCloud } from "@/components/landing/logo-cloud";
import { MetricsTestimonial } from "@/components/landing/metrics-testimonial";
import { PricingSection } from "@/components/landing/pricing-section";
import { WorkflowSection } from "@/components/landing/workflow-section";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function HomePage() {
  useDocumentTitle("LeadScope AI");

  return (
    <div className="min-h-screen bg-background text-foreground">
      <LandingNav />
      <main>
        <Hero />
        <LogoCloud />
        <FeaturesBento />
        <EvidenceSection />
        <WorkflowSection />
        <MetricsTestimonial />
        <PricingSection />
        <FaqSection />
        <CtaSection />
      </main>
      <LandingFooter />
    </div>
  );
}
