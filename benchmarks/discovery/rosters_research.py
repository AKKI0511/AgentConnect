"""Large research roster (>20): translation, jurisdictions, datasets."""

from __future__ import annotations

from benchmarks.discovery.types import Roster, profile, skill

ROSTER_RESEARCH = Roster(
    id="roster_research",
    members={
        "translate_en_es": profile(
            summary="Translates English source text into Spanish for product copy.",
            description=(
                "Direction is English to Spanish only. Required context: English "
                "source and product locale notes. Expected outcome: Spanish "
                "copy preserving placeholders. Does not translate Spanish into "
                "English; that is translate_es_en. Does not do legal certified "
                "translations."
            ),
            tags=["translation", "en-es"],
            skills=[
                skill(
                    "en_to_es",
                    (
                        "Translate English marketing or UI strings into Spanish. "
                        "Excludes Spanish-to-English and certified legal work."
                    ),
                    examples=[
                        "Translate 'Start free trial' into Spanish for MX.",
                        "Localize the pricing FAQ from English to Spanish.",
                    ],
                    tags=["en-es", "product-copy"],
                ),
            ],
        ),
        "translate_es_en": profile(
            summary="Translates Spanish source text into English for product copy.",
            description=(
                "Direction is Spanish to English only. Required context: Spanish "
                "source. Expected outcome: English copy. Does not translate "
                "English into Spanish."
            ),
            tags=["translation", "es-en"],
            skills=[
                skill(
                    "es_to_en",
                    (
                        "Translate Spanish product copy into English. Excludes "
                        "English-to-Spanish direction."
                    ),
                    examples=[
                        "Translate this Spanish onboarding email into English.",
                    ],
                    tags=["es-en", "product-copy"],
                ),
            ],
        ),
        "translate_en_fr": profile(
            summary="Translates English source text into French for product copy.",
            description=("English to French only. Not Spanish pairs and not FR→EN."),
            tags=["translation", "en-fr"],
            skills=[
                skill(
                    "en_to_fr",
                    (
                        "Translate English UI strings into French. Excludes "
                        "French-to-English."
                    ),
                    examples=[
                        "Translate the empty-state string into French for FR.",
                    ],
                    tags=["en-fr"],
                ),
            ],
        ),
        "translate_fr_en": profile(
            summary="Translates French source text into English for product copy.",
            description=("French to English only. Not English-to-French."),
            tags=["translation", "fr-en"],
            skills=[
                skill(
                    "fr_to_en",
                    ("Translate French product copy into English. Excludes EN→FR."),
                    examples=[
                        "Translate this French help article into English.",
                    ],
                    tags=["fr-en"],
                ),
            ],
        ),
        "translate_generalist": profile(
            summary="General translation helper for many language pairs.",
            description=(
                "Broad translator that claims many pairs without deep locale "
                "notes. Prefer directional specialists when direction matters."
            ),
            tags=["translation", "generalist"],
            skills=[
                skill(
                    "translate_text",
                    (
                        "Attempt translation between common pairs. Weaker on "
                        "strict direction constraints and locale QA."
                    ),
                    examples=[
                        "Translate this somehow between English and Spanish.",
                    ],
                    tags=["general"],
                ),
            ],
        ),
        "law_us_federal": profile(
            summary="Researches United States federal statutes and regulations.",
            description=(
                "US federal materials only (USC, CFR, agency guidance). Required "
                "context: question and preferred sources. Does not advise on "
                "EU GDPR substance or UK statutes as primary law. Not a "
                "substitute for counsel."
            ),
            tags=["legal-research", "us-federal"],
            skills=[
                skill(
                    "research_us_federal",
                    (
                        "Find and summarize US federal statutory or regulatory "
                        "material. Excludes EU and UK primary research."
                    ),
                    examples=[
                        "Summarize FTC Act authority relevant to dark patterns.",
                    ],
                    tags=["us", "statutes"],
                ),
            ],
        ),
        "law_eu_gdpr": profile(
            summary="Researches EU GDPR articles and EDPB guidance.",
            description=(
                "EU data-protection research focused on GDPR and EDPB. Does "
                "not treat US federal statutes as the primary corpus."
            ),
            tags=["legal-research", "eu-gdpr"],
            skills=[
                skill(
                    "research_gdpr",
                    (
                        "Summarize GDPR articles and EDPB guidance for a "
                        "processing question. Excludes US federal primary law."
                    ),
                    examples=[
                        "What does Art. 6 say about legitimate interests for B2B email?",
                    ],
                    tags=["gdpr", "eu"],
                ),
            ],
        ),
        "law_uk": profile(
            summary="Researches United Kingdom statutes and ICO guidance.",
            description=(
                "UK primary materials and ICO guidance. Not US federal or EU "
                "GDPR as the home corpus."
            ),
            tags=["legal-research", "uk"],
            skills=[
                skill(
                    "research_uk_law",
                    (
                        "Summarize UK statutory or ICO material for a question. "
                        "Excludes US Code primary research."
                    ),
                    examples=[
                        "Summarize PECR rules for marketing email consent.",
                    ],
                    tags=["uk", "ico"],
                ),
            ],
        ),
        "dataset_sec_edgar": profile(
            summary="Queries SEC EDGAR filings the Team already mirrors.",
            description=(
                "Accessible corpus: mirrored SEC EDGAR filings. Required "
                "context: ticker or CIK and form type. Cannot query datasets "
                "the Team does not mirror, such as proprietary credit tapes."
            ),
            tags=["datasets", "edgar"],
            skills=[
                skill(
                    "search_edgar",
                    (
                        "Search mirrored EDGAR filings for a ticker and form. "
                        "Excludes datasets outside the EDGAR mirror."
                    ),
                    examples=[
                        "Find the latest 10-K risk factors for ticker ACME.",
                    ],
                    tags=["edgar", "filings"],
                ),
            ],
        ),
        "dataset_patents": profile(
            summary="Queries the Team's mirrored USPTO patent grant corpus.",
            description=(
                "Accessible corpus: mirrored USPTO grants. Cannot search EDGAR "
                "or clinical-trial registries."
            ),
            tags=["datasets", "patents"],
            skills=[
                skill(
                    "search_patents",
                    (
                        "Search mirrored USPTO grants by assignee or CPC. "
                        "Excludes EDGAR and clinical registries."
                    ),
                    examples=[
                        "Find recent grants assigned to ACME on class G06F.",
                    ],
                    tags=["uspto"],
                ),
            ],
        ),
        "dataset_clinical": profile(
            summary="Queries mirrored ClinicalTrials.gov records the Team hosts.",
            description=(
                "Accessible corpus: ClinicalTrials.gov mirror. Not EDGAR or "
                "patent grants."
            ),
            tags=["datasets", "clinical"],
            skills=[
                skill(
                    "search_trials",
                    (
                        "Search mirrored trial records by condition and phase. "
                        "Excludes SEC filings."
                    ),
                    examples=[
                        "List phase 3 trials for condition X updated this year.",
                    ],
                    tags=["trials"],
                ),
            ],
        ),
        "dataset_opensource_licenses": profile(
            summary="Looks up OSI license texts and SPDX identifiers.",
            description=("License corpus only. Not financial filings or patents."),
            tags=["datasets", "licenses"],
            skills=[
                skill(
                    "lookup_license",
                    (
                        "Return SPDX id and summary obligations for a license. "
                        "Excludes EDGAR search."
                    ),
                    examples=[
                        "Summarize obligations for Apache-2.0 versus GPL-3.0.",
                    ],
                    tags=["spdx"],
                ),
            ],
        ),
        "citation_formatter": profile(
            summary="Formats bibliographic citations in APA or Bluebook styles.",
            description=(
                "Citation formatting only. Does not perform primary legal "
                "research in a jurisdiction."
            ),
            tags=["citations", "writing"],
            skills=[
                skill(
                    "format_citation",
                    (
                        "Format a source into APA or Bluebook. Excludes "
                        "jurisdiction research."
                    ),
                    examples=[
                        "Bluebook cite this USC section for a memo.",
                    ],
                    tags=["bluebook"],
                ),
            ],
        ),
        "summarize_pdf": profile(
            summary="Summarizes uploaded PDFs into bullet findings.",
            description=(
                "General PDF summarizer. Not tied to a jurisdiction corpus or "
                "a mirrored dataset specialty."
            ),
            tags=["summarization", "pdf"],
            skills=[
                skill(
                    "summarize_document",
                    (
                        "Summarize an uploaded PDF into bullets. Excludes "
                        "authoritative EDGAR or patent corpus search."
                    ),
                    examples=[
                        "Summarize this 40-page PDF into five findings.",
                    ],
                    tags=["pdf"],
                ),
            ],
        ),
        "web_generalist": profile(
            summary="Searches the public web for almost any research question.",
            description=(
                "Broad web searcher. Useful distractor when a mirrored dataset "
                "or jurisdiction specialist is required. May invent coverage."
            ),
            tags=["research", "generalist", "broad"],
            skills=[
                skill(
                    "web_search",
                    (
                        "Search the public web and draft an answer. Weaker when "
                        "a specific mirrored corpus or jurisdiction is required."
                    ),
                    examples=[
                        "Look up whatever you can about this company.",
                    ],
                    tags=["web"],
                ),
            ],
        ),
        "glossary_builder": profile(
            summary="Builds bilingual glossaries from approved term lists.",
            description=(
                "Glossary construction, not full document translation in a "
                "fixed direction."
            ),
            tags=["translation", "glossary"],
            skills=[
                skill(
                    "build_glossary",
                    (
                        "Build a glossary from term pairs. Excludes translating "
                        "full UI string files in a single direction."
                    ),
                    examples=[
                        "Build an EN/ES glossary from the product term sheet.",
                    ],
                    tags=["glossary"],
                ),
            ],
        ),
        "mt_postedit": profile(
            summary="Post-edits machine translation draft without changing direction.",
            description=(
                "Edits an existing MT draft for fluency. Caller must already "
                "know source and target; this Agent does not choose direction."
            ),
            tags=["translation", "postedit"],
            skills=[
                skill(
                    "postedit_mt",
                    (
                        "Post-edit an MT draft for fluency and placeholder "
                        "integrity. Does not pick EN→ES versus ES→EN."
                    ),
                    examples=[
                        "Post-edit this MT Spanish draft for placeholders.",
                    ],
                    tags=["postedit"],
                ),
            ],
        ),
        "market_research_us": profile(
            summary="Compiles US market sizing notes from public sources.",
            description=(
                "US market research notes. Not EU GDPR legal research and not "
                "EDGAR primary filing extraction."
            ),
            tags=["market", "us"],
            skills=[
                skill(
                    "us_market_brief",
                    (
                        "Draft a short US market brief from public sources. "
                        "Excludes GDPR article analysis."
                    ),
                    examples=[
                        "Brief the US SMB spend for category Y.",
                    ],
                    tags=["market"],
                ),
            ],
        ),
        "market_research_eu": profile(
            summary="Compiles EU market sizing notes from public sources.",
            description=("EU market research. Not US federal legal research."),
            tags=["market", "eu"],
            skills=[
                skill(
                    "eu_market_brief",
                    ("Draft a short EU market brief. Excludes US Code research."),
                    examples=[
                        "Brief EU SMB spend for category Y.",
                    ],
                    tags=["market"],
                ),
            ],
        ),
        "stats_helper": profile(
            summary="Computes basic statistics on caller-provided tables.",
            description=(
                "Descriptive stats on provided CSV/tables. Does not fetch "
                "mirrored external corpora."
            ),
            tags=["stats", "tables"],
            skills=[
                skill(
                    "describe_table",
                    (
                        "Compute mean/median/quantiles on a provided table. "
                        "Excludes EDGAR or patent corpus retrieval."
                    ),
                    examples=[
                        "Describe conversion rates in the attached CSV.",
                    ],
                    tags=["descriptive"],
                ),
            ],
        ),
        "chart_maker": profile(
            summary="Builds simple charts from caller-provided series.",
            description=("Charting only. Not dataset retrieval from mirrored corpora."),
            tags=["charts", "viz"],
            skills=[
                skill(
                    "make_chart",
                    (
                        "Render a simple chart from provided series. Excludes "
                        "searching patents or filings."
                    ),
                    examples=[
                        "Bar chart of monthly signups from this table.",
                    ],
                    tags=["chart"],
                ),
            ],
        ),
        "policy_compare": profile(
            summary="Compares two internal policy PDFs for wording diffs.",
            description=(
                "Internal policy diffing. Not jurisdiction primary-law research."
            ),
            tags=["policy", "diff"],
            skills=[
                skill(
                    "diff_policies",
                    (
                        "Diff two internal policy documents. Excludes GDPR "
                        "article research against EDPB."
                    ),
                    examples=[
                        "Diff v3 and v4 of the internal retention policy.",
                    ],
                    tags=["diff"],
                ),
            ],
        ),
        "negated_translator": profile(
            summary="Translation coordinator that does not produce translations.",
            description=(
                "Coordinates handoffs and style guides. Explicitly does not "
                "translate strings in any language pair despite the name. "
                "Negated capability: no EN↔ES or EN↔FR translation output."
            ),
            tags=["translation", "coordination", "negated"],
            skills=[
                skill(
                    "assign_translation_ticket",
                    (
                        "Create a ticket for human translators. Does not "
                        "produce translated text in any direction."
                    ),
                    examples=[
                        "Open a ticket for the Spanish homepage strings.",
                    ],
                    tags=["ticket"],
                ),
            ],
        ),
        "misleading_global_counsel": profile(
            summary="Global counsel-style researcher for any jurisdiction.",
            description=(
                "Broad, overstated Profile claiming worldwide legal research. "
                "In practice only drafts intake notes and cannot cite US, EU, "
                "or UK primary materials authoritatively. Misleading distractor."
            ),
            tags=["legal-research", "broad", "misleading"],
            skills=[
                skill(
                    "intake_legal_question",
                    (
                        "Capture a legal research question and suggest which "
                        "specialist jurisdiction desk should own it. Does not "
                        "deliver primary-law answers."
                    ),
                    examples=[
                        "Intake a question about email marketing rules somewhere.",
                    ],
                    tags=["intake"],
                ),
            ],
        ),
        "late_patent_classifier": profile(
            summary="Research utility with several ordinary writing Skills.",
            description=(
                "Routine research helper. Distinguishing capability—CPC "
                "classification suggestions against the mirrored patent "
                "corpus—appears only as the final Skill. Prefer when the "
                "need is CPC hints, not a full patent search narrative."
            ),
            tags=["research", "patents", "utility"],
            skills=[
                skill(
                    "outline_memo",
                    "Outline a research memo from bullets.",
                    examples=["Outline a memo on battery patents."],
                    tags=["writing"],
                ),
                skill(
                    "extract_quotes",
                    "Extract quotable sentences from pasted text.",
                    examples=["Extract three quotes from this abstract."],
                    tags=["extract"],
                ),
                skill(
                    "shorten_abstract",
                    "Shorten an abstract to a word budget.",
                    examples=["Cut this abstract to 80 words."],
                    tags=["edit"],
                ),
                skill(
                    "list_open_questions",
                    "List open questions remaining in a research thread.",
                    examples=["What is still unknown in this thread?"],
                    tags=["meta"],
                ),
                skill(
                    "suggest_cpc_codes",
                    (
                        "Suggest CPC classification codes for an invention "
                        "disclosure using the mirrored USPTO corpus. Required "
                        "context: short invention summary. Expected outcome: "
                        "ranked CPC candidates with short rationales. This "
                        "Skill appears late in the Profile on purpose."
                    ),
                    examples=[
                        "Suggest CPC codes for a on-device ML scheduling method.",
                    ],
                    tags=["cpc", "patents"],
                ),
            ],
        ),
        "corpus_librarian": profile(
            summary="Explains which mirrored datasets the Team can legally query.",
            description=(
                "Meta guide to accessible corpora. Does not run EDGAR or "
                "patent queries itself."
            ),
            tags=["datasets", "meta"],
            skills=[
                skill(
                    "list_accessible_corpora",
                    (
                        "List mirrored datasets and their license constraints. "
                        "Excludes executing a filing or patent search."
                    ),
                    examples=[
                        "Which corpora can we query for company risk factors?",
                    ],
                    tags=["catalog"],
                ),
            ],
        ),
    },
)
