import type { AuditFinding, AuditFindingStatus, ProposalLanguage } from "@/types/proposals";

/**
 * Words printed on the presence audit. Like the proposal, they follow the
 * document's language, not the salesperson's UI language.
 */
export interface AuditLabels {
  docType: string;
  preparedFor: string;
  date: string;
  category: string;
  location: string;
  website: string;
  summaryOpportunities: (count: number) => string;
  summaryStrong: string;
  summaryIntro: string;
  checksTitle: string;
  status: Record<AuditFindingStatus, string>;
  benchmarkTitle: (count: number) => string;
  benchmarkYou: string;
  benchmarkMedian: string;
  benchmarkRating: string;
  benchmarkReviews: string;
  benchmarkWebsite: string;
  yes: string;
  no: string;
  evidenceTitle: string;
  source: string;
  noteTitle: string;
  nextStepTitle: string;
  nextStepDefault: string;
  method: (date: string) => string;
  footerKind: string;
}

export interface FindingText {
  title: string;
  detail: string;
}

function number(language: ProposalLanguage, value: number, digits = 0): string {
  return new Intl.NumberFormat(language === "ar" ? "ar" : "en", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

const EN: AuditLabels = {
  docType: "ONLINE PRESENCE AUDIT",
  preparedFor: "PREPARED FOR",
  date: "Date",
  category: "Category",
  location: "Location",
  website: "Website",
  summaryOpportunities: (count) =>
    count === 1 ? "1 opportunity to win more customers" : `${count} opportunities to win more customers`,
  summaryStrong: "Your online presence is in good shape",
  summaryIntro:
    "We looked at how your business appears to someone searching for it today, and compared it with similar businesses nearby.",
  checksTitle: "What we checked",
  status: { good: "Strength", improve: "Opportunity", missing: "Missing" },
  benchmarkTitle: (count) => `Compared with ${count} similar businesses nearby`,
  benchmarkYou: "You",
  benchmarkMedian: "Typical nearby",
  benchmarkRating: "Rating",
  benchmarkReviews: "Reviews",
  benchmarkWebsite: "Have a website",
  yes: "Yes",
  no: "No",
  evidenceTitle: "What we noticed",
  source: "Source",
  noteTitle: "A note from us",
  nextStepTitle: "Next step",
  nextStepDefault: "A 15-minute call to walk through these findings and the quickest wins. No obligation.",
  method: (date) =>
    `Based on publicly available information collected up to ${date}. "Typical nearby" is the median of the businesses found in the same search. Figures may have changed since.`,
  footerKind: "PRESENCE AUDIT",
};

const AR: AuditLabels = {
  docType: "تقرير الحضور الرقمي",
  preparedFor: "مُعدّ لـ",
  date: "التاريخ",
  category: "النشاط",
  location: "الموقع",
  website: "الموقع الإلكتروني",
  summaryOpportunities: (count) =>
    count === 1 ? "فرصة واحدة لكسب عملاء أكثر" : `${number("ar", count)} فرص لكسب عملاء أكثر`,
  summaryStrong: "حضورك الرقمي في وضع جيد",
  summaryIntro: "راجعنا كيف يظهر نشاطك لمن يبحث عنه اليوم، وقارنّاه بأنشطة مشابهة قريبة منك.",
  checksTitle: "ما الذي راجعناه",
  status: { good: "نقطة قوة", improve: "فرصة تحسين", missing: "غير موجود" },
  benchmarkTitle: (count) => `مقارنة مع ${number("ar", count)} نشاطًا مشابهًا قريبًا`,
  benchmarkYou: "نشاطك",
  benchmarkMedian: "المعتاد في منطقتك",
  benchmarkRating: "التقييم",
  benchmarkReviews: "المراجعات",
  benchmarkWebsite: "لديهم موقع",
  yes: "نعم",
  no: "لا",
  evidenceTitle: "ما لاحظناه",
  source: "المصدر",
  noteTitle: "ملاحظة منّا",
  nextStepTitle: "الخطوة التالية",
  nextStepDefault: "مكالمة مدتها 15 دقيقة نستعرض فيها هذه النتائج وأسرع المكاسب، دون أي التزام.",
  method: (date) =>
    `مبني على معلومات متاحة للعموم حتى ${date}. "المعتاد في منطقتك" هو الوسيط بين الأنشطة التي ظهرت في البحث نفسه. قد تكون الأرقام تغيّرت منذ ذلك الحين.`,
  footerKind: "تقرير الحضور الرقمي",
};

export function auditLabels(language: ProposalLanguage): AuditLabels {
  return language === "ar" ? AR : EN;
}

/** The sentence a finding prints, worded from its code and numbers. */
export function findingText(finding: AuditFinding, language: ProposalLanguage): FindingText {
  const ar = language === "ar";
  const v = finding.values;
  const has = (key: string) => typeof v[key] === "number";
  const n = (key: string, digits = 0) => number(language, v[key] ?? 0, digits);

  switch (finding.key) {
    case "website":
      if (finding.status === "good") {
        return ar
          ? { title: "لديك موقع إلكتروني", detail: "يمكن للعملاء العثور عليك والتحقق منك قبل التواصل." }
          : { title: "Website is live", detail: "Customers can find you and check you out before they get in touch." };
      }
      return ar
        ? {
            title: "لم نجد موقعًا إلكترونيًا",
            detail: `معظم العملاء يبحثون عن النشاط على الإنترنت قبل الاتصال.${has("peer_pct") ? ` ${n("peer_pct")}% من الأنشطة المشابهة القريبة لديها موقع.` : ""}`,
          }
        : {
            title: "No website found",
            detail: `Most customers look a business up online before they call.${has("peer_pct") ? ` ${n("peer_pct")}% of similar businesses nearby have one.` : ""}`,
          };
    case "rating":
      if (finding.status === "missing") {
        return ar
          ? { title: "لا يوجد تقييم عام", detail: "العملاء الجدد يعتمدون على النجوم والمراجعات للاختيار بين الخيارات." }
          : { title: "No public rating yet", detail: "New customers rely on stars and reviews to choose between options." };
      }
      if (finding.status === "good") {
        return ar
          ? { title: `تقييم ${n("rating", 1)} ★`, detail: "سمعة قوية تساعد العملاء على اختيارك بثقة." }
          : { title: `${n("rating", 1)}★ rating`, detail: "A strong reputation that helps customers choose you with confidence." };
      }
      return ar
        ? {
            title: `تقييم ${n("rating", 1)} ★${has("peer_median") ? ` مقابل ${n("peer_median", 1)} ★ في منطقتك` : ""}`,
            detail: "العملاء يقارنون النجوم قبل الاختيار. الرد على المراجعات وطلبها من العملاء الراضين يرفع التقييم بسرعة.",
          }
        : {
            title: `${n("rating", 1)}★ rating${has("peer_median") ? ` vs ${n("peer_median", 1)}★ nearby` : ""}`,
            detail: "Customers compare stars before they choose. Replying to reviews and asking happy customers for one lifts it quickly.",
          };
    case "reviews":
      if (finding.status === "missing") {
        return ar
          ? { title: "لا توجد مراجعات بعد", detail: "المراجعات الحديثة هي أول ما يقرؤه العميل الجديد." }
          : { title: "No reviews yet", detail: "Recent reviews are the first thing a new customer reads." };
      }
      if (finding.status === "good") {
        return ar
          ? { title: `${n("count")} مراجعة`, detail: "عدد كافٍ من المراجعات يبني الثقة." }
          : { title: `${n("count")} reviews`, detail: "Enough reviews to build trust with new customers." };
      }
      return ar
        ? {
            title: `${n("count")} مراجعة${has("peer_median") ? ` مقابل ${n("peer_median")} في منطقتك` : ""}`,
            detail: "طلب مراجعة بسيط بعد كل زيارة يسدّ هذه الفجوة خلال أسابيع.",
          }
        : {
            title: `${n("count")} reviews${has("peer_median") ? ` vs ${n("peer_median")} nearby` : ""}`,
            detail: "A simple review request after each visit closes this gap within weeks.",
          };
    case "phone":
      return finding.status === "good"
        ? ar
          ? { title: "رقم الهاتف ظاهر", detail: "العملاء الجاهزون للحجز يستطيعون الاتصال مباشرة." }
          : { title: "Phone number listed", detail: "Customers ready to book can call you straight away." }
        : ar
          ? { title: "لا يظهر رقم هاتف", detail: "العميل الجاهز للحجز يريد الاتصال فورًا." }
          : { title: "No phone number listed", detail: "A customer who is ready to book wants to call right now." };
    case "email":
      return finding.status === "good"
        ? ar
          ? { title: "بريد تواصل منشور", detail: "طريقة سهلة للاستفسارات والطلبات خارج ساعات العمل." }
          : { title: "Contact email published", detail: "An easy way in for questions and requests after hours." }
        : ar
          ? { title: "لا يوجد بريد تواصل منشور", detail: "بعض العملاء يفضّلون الكتابة على الاتصال، خصوصًا خارج ساعات العمل." }
          : { title: "No public contact email", detail: "Some customers prefer writing to calling, especially after hours." };
    case "social":
      return finding.status === "good"
        ? ar
          ? { title: "صفحة أعمال موجودة", detail: "حضور مهني يعزز الثقة لدى العملاء والشركاء." }
          : { title: "Business profile found", detail: "A professional presence that builds trust with customers and partners." }
        : ar
          ? { title: "لم نجد صفحة أعمال", detail: "صفحة أعمال بسيطة تجعل نشاطك أسهل في العثور عليه والتحقق منه." }
          : { title: "No business profile found", detail: "A simple business page makes you easier to find and to verify." };
  }
}

export function opportunityCount(findings: AuditFinding[]): number {
  return findings.filter((finding) => finding.status !== "good").length;
}

/** A short cover email for sending the PDF, in the document's language. */
export function auditCoverEmail({
  language,
  companyName,
  findings,
  senderName,
}: {
  language: ProposalLanguage;
  companyName: string;
  findings: AuditFinding[];
  senderName: string;
}): string {
  const top = findings
    .filter((finding) => finding.status !== "good")
    .slice(0, 3)
    .map((finding) => `- ${findingText(finding, language).title}`);
  if (language === "ar") {
    return [
      `الموضوع: تقرير مختصر عن الحضور الرقمي لـ ${companyName}`,
      "",
      "مرحبًا،",
      "",
      `أعددنا تقريرًا من صفحة واحدة يوضح كيف يظهر ${companyName} لمن يبحث عنه اليوم، مقارنةً بأنشطة مشابهة قريبة.`,
      ...(top.length > 0 ? ["", "أبرز ما وجدناه:", ...top] : []),
      "",
      "التقرير مرفق. هل يناسبك اتصال لمدة 15 دقيقة هذا الأسبوع لنستعرضه معًا؟",
      "",
      "مع التحية،",
      senderName,
    ].join("\n");
  }
  return [
    `Subject: A quick online presence check for ${companyName}`,
    "",
    "Hi,",
    "",
    `We put together a one-page audit of how ${companyName} shows up to someone searching for it today, compared with similar businesses nearby.`,
    ...(top.length > 0 ? ["", "The main things we found:", ...top] : []),
    "",
    "The audit is attached. Would a 15-minute call this week to walk through it be useful?",
    "",
    "Best regards,",
    senderName,
  ].join("\n");
}

/** The lead's own figures for the benchmark table, read from its findings. */
export function ownFigures(findings: AuditFinding[]): {
  rating: number | null;
  reviews: number | null;
  website: boolean;
} {
  const byKey = new Map(findings.map((finding) => [finding.key, finding]));
  const rating = byKey.get("rating")?.values.rating;
  const reviews = byKey.get("reviews")?.values.count;
  return {
    rating: typeof rating === "number" ? rating : null,
    reviews: typeof reviews === "number" ? reviews : byKey.get("reviews")?.status === "missing" ? 0 : null,
    website: byKey.get("website")?.status === "good",
  };
}
