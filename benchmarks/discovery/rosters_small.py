"""Specialist Profile rosters for the discovery corpus.

Profiles use only AgentProfile / Skill fields. Scope, required context,
expected outcomes, and exclusions live in prose and examples so a human
reviewer can separate near-neighbors.
"""

from __future__ import annotations

from benchmarks.discovery.types import Roster, profile, skill

# ---------------------------------------------------------------------------
# roster_commerce — 10 members (elbow: at most 10 other members)
# Near-neighbors: merchant refunds vs card-network chargebacks; generalist.
# ---------------------------------------------------------------------------

ROSTER_COMMERCE = Roster(
    id="roster_commerce",
    members={
        "refund_ops": profile(
            summary="Handles merchant-side purchase refunds and goodwill credits.",
            description=(
                "Use when a customer already received the goods or service and the "
                "merchant still controls the original payment capture. Required "
                "context: order id, capture amount, refund amount, and reason code "
                "from the storefront. Expected outcome: a posted partial or full "
                "refund on the merchant processor with a customer-facing status. "
                "Does not file card-network disputes, representments, or "
                "chargeback rebuttals; those need the chargeback specialist."
            ),
            tags=["payments", "merchant", "refunds"],
            skills=[
                skill(
                    "issue_refund",
                    (
                        "Post a full or partial refund against a captured merchant "
                        "charge when the storefront still owns the funds. Requires "
                        "order id and amount. Excludes chargeback case filing."
                    ),
                    examples=[
                        "Refund $42.10 on order ORD-9182 for a damaged sweater.",
                        "Issue a goodwill credit of $15 on subscription SUB-44.",
                    ],
                    tags=["refund", "capture"],
                ),
                skill(
                    "explain_refund_timeline",
                    (
                        "Explain when a merchant refund appears on the customer's "
                        "statement. Not for network dispute timelines."
                    ),
                    examples=[
                        "When will ORD-9182's refund show on a Visa debit card?",
                    ],
                    tags=["customer-comms"],
                ),
            ],
        ),
        "chargeback_desk": profile(
            summary="Works card-network chargebacks and representment packages.",
            description=(
                "Use after a card network opens a dispute (chargeback) against a "
                "captured payment. Required context: case id, reason code, due "
                "date, and evidence the merchant can supply. Expected outcome: a "
                "filed representment or a documented acceptance of liability. "
                "Does not issue ordinary storefront refunds while the merchant "
                "still controls the capture; that is refund_ops work."
            ),
            tags=["payments", "chargebacks", "networks"],
            skills=[
                skill(
                    "assemble_representment",
                    (
                        "Build a chargeback representment package for Visa, "
                        "Mastercard, or Amex reason codes. Needs case id and "
                        "shipping or usage evidence. Not for goodwill refunds."
                    ),
                    examples=[
                        "Assemble evidence for CB-5512 reason 13.1 merchandise not received.",
                        "Draft rebuttal for CB-8821 fraud claim with AVS and 3DS logs.",
                    ],
                    tags=["representment", "evidence"],
                ),
                skill(
                    "track_dispute_deadlines",
                    (
                        "List open network disputes with filing deadlines and "
                        "missing evidence. Excludes merchant-initiated refunds."
                    ),
                    examples=[
                        "Which chargebacks close this week without a response?",
                    ],
                    tags=["deadlines"],
                ),
            ],
        ),
        "billing_generalist": profile(
            summary="General billing help for invoices, plans, and payment questions.",
            description=(
                "Broad first-line billing agent for plan changes, invoice copies, "
                "and payment method updates. Useful when the request is vague. "
                "Not the specialist for chargeback representments or complex "
                "partial refunds with inventory restocking rules."
            ),
            tags=["billing", "generalist"],
            skills=[
                skill(
                    "answer_billing_question",
                    (
                        "Answer general questions about invoices, plan tiers, and "
                        "payment methods. Escalates specialized refund or "
                        "chargeback work rather than owning it."
                    ),
                    examples=[
                        "What does the Pro plan include this month?",
                        "How do I update the card on file for team ACME?",
                    ],
                    tags=["support"],
                ),
            ],
        ),
        "subscription_renewals": profile(
            summary="Manages subscription renewals, proration, and plan switches.",
            description=(
                "Handles upcoming renewals, mid-cycle plan changes, and proration "
                "math. Required context: subscription id and target plan. Does "
                "not process one-off product refunds or card-network disputes."
            ),
            tags=["subscriptions", "billing"],
            skills=[
                skill(
                    "change_plan",
                    (
                        "Switch a live subscription between plans with proration. "
                        "Excludes one-time order refunds and chargebacks."
                    ),
                    examples=[
                        "Move SUB-901 from Basic to Pro effective next cycle.",
                    ],
                    tags=["proration"],
                ),
            ],
        ),
        "payout_reconciliation": profile(
            summary="Reconciles marketplace seller payouts against settlements.",
            description=(
                "Matches seller payout batches to processor settlements. Required "
                "context: payout batch id and currency. Not for consumer refunds "
                "or chargeback cases."
            ),
            tags=["payouts", "marketplace"],
            skills=[
                skill(
                    "reconcile_payout_batch",
                    (
                        "Explain variances between a seller payout and the "
                        "settlement file. Excludes buyer refunds."
                    ),
                    examples=[
                        "Why is batch PAY-330 short $120 versus the settlement?",
                    ],
                    tags=["reconciliation"],
                ),
            ],
        ),
        "tax_invoice": profile(
            summary="Issues tax-compliant invoices and credit notes for B2B sales.",
            description=(
                "Produces VAT/GST invoices and credit notes. Required context: "
                "buyer tax id and jurisdiction. Does not move money on card "
                "networks or file chargebacks."
            ),
            tags=["tax", "invoicing"],
            skills=[
                skill(
                    "issue_credit_note",
                    (
                        "Create a tax credit note for a corrected B2B invoice. "
                        "Not a card refund or dispute filing."
                    ),
                    examples=[
                        "Credit note for INV-441 after a pricing error in DE.",
                    ],
                    tags=["credit-note"],
                ),
            ],
        ),
        "fraud_review": profile(
            summary="Reviews risky orders before capture using rules and signals.",
            description=(
                "Pre-capture fraud screening for new orders. Required context: "
                "order payload and risk score. Does not handle post-capture "
                "refunds or open chargeback cases."
            ),
            tags=["fraud", "risk"],
            skills=[
                skill(
                    "review_risky_order",
                    (
                        "Approve, hold, or reject an order before capture based "
                        "on fraud signals. Excludes after-the-fact refunds."
                    ),
                    examples=[
                        "Review ORD-1200 with velocity spike from a new device.",
                    ],
                    tags=["pre-capture"],
                ),
            ],
        ),
        "dunning_collections": profile(
            summary="Retries failed recurring charges and manages dunning emails.",
            description=(
                "Owns soft and hard declines on recurring billing. Required "
                "context: subscription id and decline code. Not for goodwill "
                "refunds or network chargeback packages."
            ),
            tags=["dunning", "retries"],
            skills=[
                skill(
                    "retry_failed_charge",
                    (
                        "Schedule smart retries and customer notices for a "
                        "failed recurring charge. Excludes chargeback rebuttals."
                    ),
                    examples=[
                        "Retry SUB-55 after a soft decline and notify the payer.",
                    ],
                    tags=["retry"],
                ),
            ],
        ),
        "ledger_adjustments": profile(
            summary="Posts internal ledger adjustments and write-offs for finance.",
            description=(
                "Accounting adjustments inside the company ledger. Required "
                "context: account codes and memo. Does not talk to card networks "
                "or storefront refund APIs."
            ),
            tags=["ledger", "finance"],
            skills=[
                skill(
                    "post_adjustment",
                    (
                        "Post a balancing ledger entry with audit memo. Not a "
                        "customer-facing refund or chargeback."
                    ),
                    examples=[
                        "Write off $8.40 rounding variance on GL-900.",
                    ],
                    tags=["adjustment"],
                ),
            ],
        ),
        "payments_helpdesk": profile(
            summary="Answers any payment question and claims wide coverage.",
            description=(
                "Broad, often overstated helpdesk that will attempt refunds, "
                "disputes, tax, and payouts without owning processor workflows. "
                "Useful as a misleading distractor when a specialist exists."
            ),
            tags=["payments", "helpdesk", "broad"],
            skills=[
                skill(
                    "triage_payment_issue",
                    (
                        "Intake almost any payment complaint and draft a generic "
                        "reply. Does not reliably complete refunds or representments."
                    ),
                    examples=[
                        "Customer is upset about a charge; please help somehow.",
                    ],
                    tags=["triage"],
                ),
            ],
        ),
    },
)

# ---------------------------------------------------------------------------
# roster_legal — 8 members (elbow: at most 10)
# Near-neighbors: contract substance/risk vs formatting/redlines cosmetics.
# ---------------------------------------------------------------------------

ROSTER_LEGAL = Roster(
    id="roster_legal",
    members={
        "contract_risk": profile(
            summary="Reviews contract substance: liability, IP, termination, and risk.",
            description=(
                "Use for substantive commercial terms: indemnities, limitation of "
                "liability caps, IP ownership, termination for convenience, and "
                "data-processing risk. Required context: the draft agreement and "
                "the deal's risk appetite. Expected outcome: issue list with "
                "recommended fallback language. Does not own style, numbering, "
                "or typography cleanups; that is formatting work."
            ),
            tags=["legal", "contracts", "risk"],
            skills=[
                skill(
                    "review_commercial_terms",
                    (
                        "Flag high-risk clauses and propose fallback wording for "
                        "liability, IP, and termination. Excludes pure formatting."
                    ),
                    examples=[
                        "Review MSA section 9 liability cap against a $2M deal.",
                        "Assess IP assignment in the SOW for a joint prototype.",
                    ],
                    tags=["substance", "liability"],
                ),
                skill(
                    "compare_fallback_positions",
                    (
                        "Compare counterparty language to playbook fallbacks. "
                        "Not for typography or table-of-contents fixes."
                    ),
                    examples=[
                        "Does their uncapped indemnity match our playbook?",
                    ],
                    tags=["playbook"],
                ),
            ],
        ),
        "contract_format": profile(
            summary="Cleans contract formatting, numbering, exhibits, and styles.",
            description=(
                "Use when the legal text is already agreed and the document needs "
                "consistent headings, cross-references, exhibit labels, and "
                "house style. Required context: the nearly final Word or DOCX "
                "file. Expected outcome: a clean formatted draft without changing "
                "operative meaning. Does not negotiate liability caps or rewrite "
                "risk allocation; escalate substance to contract_risk."
            ),
            tags=["legal", "contracts", "formatting"],
            skills=[
                skill(
                    "normalize_numbering",
                    (
                        "Fix section numbering, cross-references, and exhibit "
                        "letters without changing operative clauses."
                    ),
                    examples=[
                        "Renumber exhibits after inserting Schedule C.",
                        "Repair broken cross-references in section 12.",
                    ],
                    tags=["numbering", "style"],
                ),
                skill(
                    "apply_house_styles",
                    (
                        "Apply firm styles for headings, defined terms, and "
                        "signature blocks. Excludes risk redlines."
                    ),
                    examples=[
                        "Apply house styles to the signature pages only.",
                    ],
                    tags=["styles"],
                ),
            ],
        ),
        "nda_intake": profile(
            summary="Triages inbound NDAs against a mutual template.",
            description=(
                "Checks one-way versus mutual NDAs for missing mutuality and "
                "term length. Not for complex MSA liability reviews or deep "
                "formatting passes."
            ),
            tags=["legal", "nda"],
            skills=[
                skill(
                    "screen_nda",
                    (
                        "Screen an NDA for mutuality, term, and residuals "
                        "clauses against the template. Escalates unusual IP."
                    ),
                    examples=[
                        "Is this one-way NDA acceptable for a vendor pitch?",
                    ],
                    tags=["nda"],
                ),
            ],
        ),
        "privacy_dpa": profile(
            summary="Reviews data processing addenda and subprocessors lists.",
            description=(
                "Focuses on GDPR/CCPA processing terms and subprocessor "
                "disclosure. Required context: DPA draft and processing "
                "activities. Not general MSA liability or formatting."
            ),
            tags=["privacy", "dpa"],
            skills=[
                skill(
                    "review_dpa",
                    (
                        "Check transfer mechanisms, audit rights, and "
                        "subprocessor notice periods in a DPA."
                    ),
                    examples=[
                        "Does this DPA allow 14-day subprocessor objection?",
                    ],
                    tags=["gdpr"],
                ),
            ],
        ),
        "employment_offer": profile(
            summary="Drafts employment offer letters and basic equity summaries.",
            description=(
                "Standard offer letters and equity vignettes for new hires. "
                "Not commercial MSA negotiation or contract formatting."
            ),
            tags=["employment", "hr-legal"],
            skills=[
                skill(
                    "draft_offer_letter",
                    (
                        "Draft an at-will offer letter with title, pay, and "
                        "start date. Excludes complex commercial contracts."
                    ),
                    examples=[
                        "Offer letter for a senior engineer in California.",
                    ],
                    tags=["offers"],
                ),
            ],
        ),
        "litigation_holds": profile(
            summary="Issues litigation holds and tracks custodian acknowledgements.",
            description=(
                "Preserve-in-place notices when a dispute is reasonably "
                "anticipated. Not for drafting commercial contracts."
            ),
            tags=["litigation", "holds"],
            skills=[
                skill(
                    "issue_hold",
                    (
                        "Issue a litigation hold to named custodians and track "
                        "acknowledgements. Excludes contract redlines."
                    ),
                    examples=[
                        "Hold for custodians on matter M-204 starting today.",
                    ],
                    tags=["preservation"],
                ),
            ],
        ),
        "legal_generalist": profile(
            summary="General legal assistant for contracts, privacy, and HR questions.",
            description=(
                "First-line legal generalist. Fine for routing, weak for deep "
                "liability analysis or meticulous formatting. Near-neighbor to "
                "both specialists without owning either depth."
            ),
            tags=["legal", "generalist"],
            skills=[
                skill(
                    "answer_legal_question",
                    (
                        "Provide a high-level answer and recommend a specialist "
                        "when risk or formatting depth is required."
                    ),
                    examples=[
                        "Is this clause unusual? Who should look at it?",
                    ],
                    tags=["intake"],
                ),
            ],
        ),
        "clause_library": profile(
            summary="Retrieves approved clause text from the playbook library.",
            description=(
                "Looks up approved fallback clauses by topic. Does not decide "
                "which risk posture to take or reformat an entire agreement."
            ),
            tags=["legal", "playbook"],
            skills=[
                skill(
                    "fetch_approved_clause",
                    (
                        "Return the approved playbook clause for a named topic. "
                        "Excludes full agreement risk review."
                    ),
                    examples=[
                        "Fetch the approved limitation of liability fallback.",
                    ],
                    tags=["library"],
                ),
            ],
        ),
    },
)
