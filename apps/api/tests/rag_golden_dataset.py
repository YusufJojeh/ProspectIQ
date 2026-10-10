"""Golden dataset for RAG retrieval-quality measurement.

31 documents and 55 labelled queries. Each positive query names the document
(by title) a salesperson should be shown; each negative query has NO relevant
document and must come back empty rather than as a confident wrong answer.

Design rules the queries follow, so the numbers mean something:

* queries are paraphrases, not copies of a document's sentences (a query that
  quotes its target verbatim only measures string matching);
* several documents deliberately overlap (three appointment/booking documents,
  three review/reputation documents, two dental documents, two pricing
  documents) so ranking has to discriminate;
* a "lexical" query shares rare terms with its target, a "semantic" query
  shares few or none. The local hashing embedder is lexical by construction,
  so the semantic bucket is expected to be the weak spot and is reported
  separately rather than averaged away.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.knowledge.constants import (
    CASE_STUDIES,
    ICP,
    INDUSTRY_PLAYBOOKS,
    OBJECTIONS,
    PRICING_GUIDANCE,
    PRODUCT_DOCS,
    SALES_PLAYBOOKS,
    SERVICES,
    WINNING_OUTREACH,
)


@dataclass(frozen=True, slots=True)
class GoldenDoc:
    title: str
    kind: str
    content: str


@dataclass(frozen=True, slots=True)
class GoldenQuery:
    query: str
    #: Titles of documents that count as a hit. Empty tuple = negative query.
    relevant: tuple[str, ...]
    #: "lexical" (shares rare terms) | "semantic" (paraphrase) | "negative"
    bucket: str


DOCS: tuple[GoldenDoc, ...] = (
    GoldenDoc("Appointment Reminder Automation", SERVICES,
        "# Appointment Reminder Automation\n\nWe build automated SMS and WhatsApp appointment reminder flows for clinics. Reminders go out 48 hours and 2 hours before each booking, with one-tap rescheduling. Typical deployment takes three weeks including calendar integration."),
    GoldenDoc("Online Booking Portal", SERVICES,
        "# Online Booking Portal\n\nA branded self-service booking page where customers pick a time slot, pay a deposit and receive a confirmation. Replaces phone-only scheduling for salons and clinics and syncs with Google Calendar."),
    GoldenDoc("Walk-in Queue Management", SERVICES,
        "# Walk-in Queue Management\n\nDigital queue tickets for busy front desks. Customers join a waiting line by scanning a QR code and receive a text when their turn is near. Reduces crowding in the waiting room."),
    GoldenDoc("Riyadh Dental Group No-Show Reduction", CASE_STUDIES,
        "# Riyadh Dental Group\n\nRiyadh Dental Group ran a 31 percent no-show rate across four branches. After deploying our reminder automation their no-show rate fell to 12 percent within two months, recovering roughly 180 appointments per month. The practice added a fifth branch the following quarter."),
    GoldenDoc("Jeddah Smile Clinic Online Booking", CASE_STUDIES,
        "# Jeddah Smile Clinic\n\nJeddah Smile Clinic moved from phone bookings to our online booking portal. Out-of-hours requests, previously lost, now make up 22 percent of new patients. Front-desk call volume dropped by a third."),
    GoldenDoc("Google Review Response Management", SERVICES,
        "# Google Review Response Management\n\nWe monitor Google reviews, draft replies in the brand voice and escalate negative feedback to the owner within four hours. Businesses that reply to reviews rank higher and convert more searchers."),
    GoldenDoc("Review Request Campaigns", SERVICES,
        "# Review Request Campaigns\n\nAfter each completed visit customers get a short message asking for a star rating. Happy customers are routed to Google, unhappy ones to a private feedback form. Increases review velocity."),
    GoldenDoc("Reputation Recovery Case Study Cafe Group", CASE_STUDIES,
        "# Cafe Group Reputation Recovery\n\nA four-location cafe group had a 3.6 star average after a supply problem. Over five months of review requests and prompt replies the average rose to 4.5 stars and weekday footfall grew by 14 percent."),
    GoldenDoc("Local SEO and Maps Optimization", SERVICES,
        "# Local SEO and Maps Optimization\n\nWe optimize Google Business Profile listings, categories, photos and posting cadence so local searchers find the business first. Includes citation cleanup across directories and consistent name, address and phone data."),
    GoldenDoc("Website Redesign for Restaurants", SERVICES,
        "# Website Redesign for Restaurants\n\nMobile-first restaurant websites with an online menu, table reservation form and integrated delivery links. Pages load in under two seconds and are built to rank for local dining searches."),
    GoldenDoc("Retainer Pricing Guidance", PRICING_GUIDANCE,
        "# Retainer Pricing Guidance\n\nStandard retainers begin at 4500 SAR per month for a single location. Multi-branch clients are quoted per branch with a 15 percent discount from the third branch onward. Never quote below the floor without approval."),
    GoldenDoc("One-off Project Pricing", PRICING_GUIDANCE,
        "# One-off Project Pricing\n\nFixed-scope projects such as a website rebuild are priced from 18000 SAR. Payment is split 50 percent on signing and 50 percent on launch. Rush delivery under three weeks adds a 20 percent surcharge."),
    GoldenDoc("Objection Too Expensive", OBJECTIONS,
        "# Objection: It Is Too Expensive\n\nAcknowledge the concern, then reframe around cost per recovered customer instead of monthly fee. Offer a three month pilot on one location. Do not discount the retainer as a first response."),
    GoldenDoc("Objection We Already Have an Agency", OBJECTIONS,
        "# Objection: We Already Have an Agency\n\nDo not attack the incumbent. Ask what results they report monthly and offer a free audit of the current Google profile to show gaps. Position as complementary specialist work."),
    GoldenDoc("Objection Need to Think About It", OBJECTIONS,
        "# Objection: I Need to Think About It\n\nThis usually means an unanswered concern. Ask which part is unclear, restate the agreed goal and propose a specific follow-up date rather than leaving it open."),
    GoldenDoc("Ideal Customer Profile Multi-Branch Clinics", ICP,
        "# Ideal Customer Profile\n\nOur best fit is a private clinic or dental group with two to ten branches, an active Google presence but weak online booking, and an owner who makes decisions directly. Avoid single-doctor practices with no growth plan."),
    GoldenDoc("Ideal Customer Profile Restaurants", ICP,
        "# Restaurant Ideal Customer\n\nIndependent restaurants and cafe groups with three or more locations, delivery-app dependence and a rating below 4.2 stars. These owners feel review pain and margin pressure from aggregator commissions."),
    GoldenDoc("Cold Outreach Opening Lines Clinics", WINNING_OUTREACH,
        "# Winning Opening Lines for Clinics\n\nLead with a specific observation: mention their Google rating and that after-hours callers cannot book. Keep the first email under 90 words and end with a single question about missed calls."),
    GoldenDoc("Cold Outreach Follow-up Sequence", WINNING_OUTREACH,
        "# Follow-up Sequence\n\nSend three follow-ups spaced 3, 7 and 14 days apart. Each adds one new piece of evidence, such as a case study or an audit finding. Stop after the third and move the lead to nurture."),
    GoldenDoc("Discovery Call Framework", SALES_PLAYBOOKS,
        "# Discovery Call Framework\n\nOpen with the prospect's goals, then quantify the problem: how many calls go unanswered, how many appointments are missed. Confirm the decision maker and budget range before proposing anything."),
    GoldenDoc("Proposal Follow-up Playbook", SALES_PLAYBOOKS,
        "# Proposal Follow-up Playbook\n\nAfter sending a proposal, call within two business days. Offer to walk through the scope and timeline together. If there is no reply after ten days, send a short closing-the-loop message."),
    GoldenDoc("Dental Industry Playbook", INDUSTRY_PLAYBOOKS,
        "# Dental Industry Playbook\n\nDental practices lose revenue to no-shows and unfilled hygiene slots. Recall reminders for six-monthly cleanings are the strongest hook. Treatment coordinators, not dentists, usually own the booking process."),
    GoldenDoc("Salon and Beauty Playbook", INDUSTRY_PLAYBOOKS,
        "# Salon and Beauty Playbook\n\nSalons depend on Instagram discovery and repeat bookings. Deposits reduce last-minute cancellations. Stylists resist software that adds admin work, so keep the flow to two taps."),
    GoldenDoc("Restaurant Industry Playbook", INDUSTRY_PLAYBOOKS,
        "# Restaurant Industry Playbook\n\nRestaurant owners judge marketing by table covers. Peak-hour capacity limits what advertising can add, so focus on filling weekday lunch and slow evenings through reviews, maps ranking and direct reservations."),
    GoldenDoc("Gym and Fitness Playbook", INDUSTRY_PLAYBOOKS,
        "# Gym and Fitness Playbook\n\nGyms churn members after the first ninety days. Onboarding messages, class booking reminders and win-back offers for lapsed members retain revenue. Trial-pass lead follow-up within an hour doubles conversion."),
    GoldenDoc("WhatsApp Business Integration Guide", PRODUCT_DOCS,
        "# WhatsApp Business Integration\n\nConnect a verified WhatsApp Business number through the official API. Message templates require approval by Meta and can take up to two days. Opt-in must be recorded before any outbound message."),
    GoldenDoc("Calendar Sync Technical Notes", PRODUCT_DOCS,
        "# Calendar Sync\n\nTwo-way synchronisation with Google Calendar and Outlook using OAuth. Conflicts are resolved in favour of the calendar entry created first. Sync latency is under a minute."),
    GoldenDoc("Data Privacy and PDPL Compliance", PRODUCT_DOCS,
        "# Data Privacy and PDPL\n\nPatient and customer data is stored in-region and encrypted at rest. We act as a data processor under the Saudi PDPL. Deletion requests are honoured within thirty days. A data processing agreement is available on request."),
    GoldenDoc("Onboarding Timeline", PRODUCT_DOCS,
        "# Onboarding Timeline\n\nWeek one covers access and audit. Week two builds integrations and message templates. Week three is testing with staff. Go-live happens in week four with daily monitoring for the first fortnight."),
    GoldenDoc("Competitor Comparison Generic Booking Apps", SALES_PLAYBOOKS,
        "# Versus Generic Booking Apps\n\nGeneric booking apps charge per seat and offer no reminder tuning. We include local-language templates, Arabic and English, and human onboarding. Emphasise the setup service, not the software."),
    GoldenDoc("Contract Terms and Cancellation", PRICING_GUIDANCE,
        "# Contract Terms and Cancellation\n\nRetainers run twelve months with a thirty day cancellation notice after the first quarter. Pilots are month-to-month. Invoices are due within fourteen days and late payments pause service."),
)


def _q(query: str, *relevant: str, bucket: str) -> GoldenQuery:
    return GoldenQuery(query=query, relevant=relevant, bucket=bucket)


QUERIES: tuple[GoldenQuery, ...] = (
    # --- lexical: shares distinctive terms with the target --------------
    _q("sms and whatsapp appointment reminders before a booking", "Appointment Reminder Automation", bucket="lexical"),
    _q("how long does calendar integration take for reminders", "Appointment Reminder Automation", bucket="lexical"),
    _q("customer self-service booking page deposit confirmation", "Online Booking Portal", bucket="lexical"),
    _q("qr code queue ticket for waiting room", "Walk-in Queue Management", bucket="lexical"),
    _q("dental group no-show rate fell across four branches", "Riyadh Dental Group No-Show Reduction", bucket="lexical"),
    _q("clinic that recovered out-of-hours patients after online booking", "Jeddah Smile Clinic Online Booking", bucket="lexical"),
    _q("draft replies to google reviews in brand voice", "Google Review Response Management", bucket="lexical"),
    _q("route happy customers to google and unhappy to private form", "Review Request Campaigns", bucket="lexical"),
    _q("cafe group rating rose from 3.6 to 4.5 stars", "Reputation Recovery Case Study Cafe Group", bucket="lexical"),
    _q("google business profile citation cleanup", "Local SEO and Maps Optimization", bucket="lexical"),
    _q("restaurant website with online menu and table reservation", "Website Redesign for Restaurants", bucket="lexical"),
    _q("what is the starting retainer price per month in SAR", "Retainer Pricing Guidance", bucket="lexical"),
    _q("discount for multi-branch clients from the third branch", "Retainer Pricing Guidance", bucket="lexical"),
    _q("website rebuild fixed price and rush surcharge", "One-off Project Pricing", bucket="lexical"),
    _q("payment split on signing and launch", "One-off Project Pricing", bucket="lexical"),
    _q("prospect says the fee is too expensive", "Objection Too Expensive", bucket="lexical"),
    _q("they already work with an agency", "Objection We Already Have an Agency", bucket="lexical"),
    _q("prospect wants to think about it", "Objection Need to Think About It", bucket="lexical"),
    _q("best fit customer private clinic two to ten branches", "Ideal Customer Profile Multi-Branch Clinics", bucket="lexical"),
    _q("restaurant groups below 4.2 stars delivery-app dependence", "Ideal Customer Profile Restaurants", bucket="lexical"),
    _q("first email under 90 words mention google rating after-hours callers", "Cold Outreach Opening Lines Clinics", bucket="lexical"),
    _q("three follow-ups spaced 3 7 and 14 days", "Cold Outreach Follow-up Sequence", bucket="lexical"),
    _q("discovery call quantify unanswered calls and missed appointments", "Discovery Call Framework", bucket="lexical"),
    _q("call within two business days after sending a proposal", "Proposal Follow-up Playbook", bucket="lexical"),
    _q("treatment coordinators own booking in dental practices", "Dental Industry Playbook", bucket="lexical"),
    _q("salon deposits reduce last-minute cancellations instagram", "Salon and Beauty Playbook", bucket="lexical"),
    _q("fill weekday lunch covers for restaurants", "Restaurant Industry Playbook", bucket="lexical"),
    _q("gym members churn after ninety days win-back", "Gym and Fitness Playbook", bucket="lexical"),
    _q("meta template approval for whatsapp business api", "WhatsApp Business Integration Guide", bucket="lexical"),
    _q("outlook and google calendar two-way sync conflicts", "Calendar Sync Technical Notes", bucket="lexical"),
    _q("saudi pdpl data processor deletion requests", "Data Privacy and PDPL Compliance", bucket="lexical"),
    _q("week by week onboarding plan and go-live", "Onboarding Timeline", bucket="lexical"),
    _q("versus generic booking apps per seat", "Competitor Comparison Generic Booking Apps", bucket="lexical"),
    _q("cancellation notice and contract length for retainers", "Contract Terms and Cancellation", bucket="lexical"),
    # --- semantic: paraphrase, little shared vocabulary ------------------
    _q("stop patients forgetting their visit", "Appointment Reminder Automation", "Riyadh Dental Group No-Show Reduction", bucket="semantic"),
    _q("let people schedule without phoning us", "Online Booking Portal", bucket="semantic"),
    _q("get more five star feedback from customers", "Review Request Campaigns", "Google Review Response Management", bucket="semantic"),
    _q("show up higher when someone searches nearby", "Local SEO and Maps Optimization", bucket="semantic"),
    _q("what should I say when they say we cannot afford it", "Objection Too Expensive", bucket="semantic"),
    _q("how do I pitch to a clinic owner by email", "Cold Outreach Opening Lines Clinics", bucket="semantic"),
    _q("how do we keep gym members from leaving", "Gym and Fitness Playbook", bucket="semantic"),
    _q("is our customer information safe and where is it kept", "Data Privacy and PDPL Compliance", bucket="semantic"),
    _q("how quickly can we be live", "Onboarding Timeline", "Appointment Reminder Automation", bucket="semantic"),
    _q("proof that reminders actually reduce missed visits", "Riyadh Dental Group No-Show Reduction", bucket="semantic"),
    _q("who is the right kind of client for us", "Ideal Customer Profile Multi-Branch Clinics", "Ideal Customer Profile Restaurants", bucket="semantic"),
    _q("what to do when a lead goes quiet after the quote", "Proposal Follow-up Playbook", "Cold Outreach Follow-up Sequence", bucket="semantic"),
    # --- negative: nothing in the corpus answers these -------------------
    _q("how to change the oil in a diesel truck", bucket="negative"),
    _q("recipe for lamb machboos", bucket="negative"),
    _q("quantum chromodynamics lattice simulation", bucket="negative"),
    _q("who won the football world cup in 2014", bucket="negative"),
    _q("kubernetes pod eviction thresholds", bucket="negative"),
    _q("symptoms of vitamin d deficiency", bucket="negative"),
    _q("best hiking trails in switzerland", bucket="negative"),
    _q("tax treatment of cryptocurrency mining income", bucket="negative"),
    _q("guitar chord progression for blues", bucket="negative"),
    _q("zzqx blorptang wumbo", bucket="negative"),
)

assert len(DOCS) >= 30 and 30 <= len(QUERIES) <= 100
assert len({d.title for d in DOCS}) == len(DOCS)
_TITLES = {d.title for d in DOCS}
for _query in QUERIES:
    for _title in _query.relevant:
        assert _title in _TITLES, _title
