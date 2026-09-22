"""Large Platform roster (>20) with staging/prod and late-capability neighbors."""

from __future__ import annotations

from benchmarks.discovery.types import Roster, profile, skill

_BOILER = (
    "This Agent follows Team safety policy, logs every action, refuses secrets "
    "in chat, and escalates unclear ownership. Shared onboarding boilerplate "
    "appears on several Profiles and is not a distinguishing capability."
)

ROSTER_PLATFORM = Roster(
    id="roster_platform",
    members={
        "staging_deploy": profile(
            summary="Deploys and rolls back services in non-production staging only.",
            description=(
                f"{_BOILER} Use for staging cluster deploys and smoke checks. "
                "Required context: service name, image tag, and staging "
                "namespace. Expected outcome: a staging rollout or rollback. "
                "Does not touch production clusters, production DNS, or "
                "customer-facing traffic. Production work belongs to prod_deploy."
            ),
            tags=["deploy", "staging", "ops"],
            skills=[
                skill(
                    "deploy_to_staging",
                    (
                        "Roll out a container image to the staging cluster and "
                        "run smoke checks. Never applies to production."
                    ),
                    examples=[
                        "Deploy payments-api:1.8.3 to staging/us-east.",
                        "Rollback staging checkout-web to the previous revision.",
                    ],
                    tags=["staging", "rollout"],
                ),
            ],
        ),
        "prod_deploy": profile(
            summary="Deploys and rolls back production services with change control.",
            description=(
                f"{_BOILER} Use for production rollouts under change tickets. "
                "Required context: approved change id, image digest, and "
                "production target. Expected outcome: a production deploy or "
                "fast rollback. Does not deploy to staging sandboxes; that is "
                "staging_deploy. Does not edit feature flags without a ticket."
            ),
            tags=["deploy", "production", "ops"],
            skills=[
                skill(
                    "deploy_to_production",
                    (
                        "Ship an approved image digest to production with "
                        "canary then full rollout. Excludes staging-only work."
                    ),
                    examples=[
                        "Ship payments-api@sha256:9f… under CHG-441 to prod.",
                        "Rollback prod checkout-web after error-budget burn.",
                    ],
                    tags=["production", "canary"],
                ),
            ],
        ),
        "feature_flags": profile(
            summary="Toggles feature flags in staging and production catalogs.",
            description=(
                f"{_BOILER} Owns flag create/update with targeting rules. "
                "Does not deploy container images."
            ),
            tags=["flags", "ops"],
            skills=[
                skill(
                    "set_flag",
                    (
                        "Enable or disable a named feature flag for a segment. "
                        "Excludes image deploys."
                    ),
                    examples=[
                        "Enable checkout_v2 for 5% of prod us-east traffic.",
                    ],
                    tags=["targeting"],
                ),
            ],
        ),
        "k8s_debug": profile(
            summary="Debugs Kubernetes pods, events, and failing probes.",
            description=(
                f"{_BOILER} Read-only cluster debugging for CrashLoop and probe "
                "failures. Does not approve production deploys."
            ),
            tags=["kubernetes", "debug"],
            skills=[
                skill(
                    "inspect_failing_pod",
                    (
                        "Explain why a pod is failing probes or crashing. "
                        "Excludes shipping a new production image."
                    ),
                    examples=[
                        "Why is checkout-web CrashLooping in prod?",
                    ],
                    tags=["probes"],
                ),
            ],
        ),
        "ci_pipeline": profile(
            summary="Repairs CI workflows, flaky tests, and cache invalidation.",
            description=(
                f"{_BOILER} Owns GitHub Actions or similar pipeline fixes. "
                "Does not deploy to staging or production clusters."
            ),
            tags=["ci", "build"],
            skills=[
                skill(
                    "fix_pipeline",
                    (
                        "Repair a failing CI job, flake, or cache key. Excludes "
                        "live cluster rollouts."
                    ),
                    examples=[
                        "Fix the flaky e2e job on main for checkout-web.",
                    ],
                    tags=["actions"],
                ),
            ],
        ),
        "secrets_rotation": profile(
            summary="Rotates service credentials in the secret store.",
            description=(
                f"{_BOILER} Rotates API keys and DB passwords with dual-write. "
                "Does not deploy application images."
            ),
            tags=["secrets", "security"],
            skills=[
                skill(
                    "rotate_secret",
                    (
                        "Rotate a named secret and verify dependents. Excludes "
                        "feature-flag toggles."
                    ),
                    examples=[
                        "Rotate the Stripe restricted key used by billing-api.",
                    ],
                    tags=["rotation"],
                ),
            ],
        ),
        "observability_dash": profile(
            summary="Builds Grafana dashboards and alert rules for services.",
            description=(
                f"{_BOILER} Creates dashboards and pages on-call when SLOs burn. "
                "Does not perform deploys."
            ),
            tags=["observability", "sre"],
            skills=[
                skill(
                    "create_dashboard",
                    (
                        "Create or update a service dashboard and alert rule. "
                        "Excludes shipping code."
                    ),
                    examples=[
                        "Add p95 latency panel for payments-api in prod.",
                    ],
                    tags=["grafana"],
                ),
            ],
        ),
        "oncall_triage": profile(
            summary="First-line on-call triage for pages and incident channels.",
            description=(
                f"{_BOILER} Acknowledges pages, pages the right owner, and "
                "captures a timeline. Does not own staging-only deploys."
            ),
            tags=["oncall", "incident"],
            skills=[
                skill(
                    "triage_page",
                    (
                        "Acknowledge a page, classify severity, and loop in "
                        "owners. Excludes unsupervised production rollbacks "
                        "without an incident channel."
                    ),
                    examples=[
                        "Triage PagerDuty page PD-901 for checkout 5xx spike.",
                    ],
                    tags=["pager"],
                ),
            ],
        ),
        "db_migrate_staging": profile(
            summary="Runs schema migrations against staging databases only.",
            description=(
                f"{_BOILER} Applies expand/contract migrations in staging. "
                "Does not run production migrations."
            ),
            tags=["database", "staging"],
            skills=[
                skill(
                    "apply_staging_migration",
                    (
                        "Apply a reviewed migration to staging and verify. "
                        "Never against production."
                    ),
                    examples=[
                        "Apply 2026_09_add_refund_reason to staging Postgres.",
                    ],
                    tags=["migrations"],
                ),
            ],
        ),
        "db_migrate_prod": profile(
            summary="Runs approved schema migrations on production databases.",
            description=(
                f"{_BOILER} Production expand/contract migrations under change "
                "control. Does not touch staging-only sandboxes."
            ),
            tags=["database", "production"],
            skills=[
                skill(
                    "apply_prod_migration",
                    (
                        "Apply an approved migration to production with "
                        "monitoring. Excludes staging-only experiments."
                    ),
                    examples=[
                        "Apply 2026_09_add_refund_reason under CHG-512 in prod.",
                    ],
                    tags=["migrations"],
                ),
            ],
        ),
        "cdn_cache": profile(
            summary="Purges CDN cache paths and warm edge caches.",
            description=(
                f"{_BOILER} Path and surrogate-key purges on the CDN. Does not "
                "deploy origin services."
            ),
            tags=["cdn", "cache"],
            skills=[
                skill(
                    "purge_path",
                    (
                        "Purge a CDN path or surrogate key and optionally warm "
                        "it. Excludes cluster deploys."
                    ),
                    examples=[
                        "Purge /pricing and warm the edge for us-east.",
                    ],
                    tags=["purge"],
                ),
            ],
        ),
        "dns_changes": profile(
            summary="Updates DNS records for services with dual control.",
            description=(
                f"{_BOILER} Creates or updates DNS A/AAAA/CNAME records. "
                "Does not roll container images."
            ),
            tags=["dns", "network"],
            skills=[
                skill(
                    "update_dns_record",
                    (
                        "Change a DNS record with dual control. Excludes "
                        "application deploys."
                    ),
                    examples=[
                        "Point api.example.com to the new prod load balancer.",
                    ],
                    tags=["dns"],
                ),
            ],
        ),
        "cert_renewal": profile(
            summary="Renews TLS certificates before expiry.",
            description=(
                f"{_BOILER} Issues and installs renewed certificates. Does not "
                "change application code."
            ),
            tags=["tls", "certs"],
            skills=[
                skill(
                    "renew_certificate",
                    (
                        "Renew a named certificate and verify handshake. "
                        "Excludes feature flags."
                    ),
                    examples=[
                        "Renew the wildcard cert for *.example.com.",
                    ],
                    tags=["tls"],
                ),
            ],
        ),
        "capacity_planning": profile(
            summary="Forecasts capacity and recommends scale targets.",
            description=(
                f"{_BOILER} Uses traffic forecasts to recommend replica counts. "
                "Does not execute production deploys."
            ),
            tags=["capacity", "sre"],
            skills=[
                skill(
                    "recommend_scale",
                    (
                        "Recommend replica or instance counts for a horizon. "
                        "Excludes performing the rollout."
                    ),
                    examples=[
                        "Recommend checkout-web replicas for Black Friday.",
                    ],
                    tags=["forecast"],
                ),
            ],
        ),
        "cost_finops": profile(
            summary="Attributes cloud spend and flags idle resources.",
            description=(
                f"{_BOILER} FinOps attribution and idle-resource reports. "
                "Does not deploy services."
            ),
            tags=["finops", "cost"],
            skills=[
                skill(
                    "report_idle_spend",
                    (
                        "List idle or oversized resources with estimated waste. "
                        "Excludes production rollouts."
                    ),
                    examples=[
                        "Which staging nodes are idle over 14 days?",
                    ],
                    tags=["waste"],
                ),
            ],
        ),
        "log_search": profile(
            summary="Searches centralized logs for incident investigation.",
            description=(
                f"{_BOILER} Structured log queries across services. Does not "
                "change cluster state."
            ),
            tags=["logs", "debug"],
            skills=[
                skill(
                    "query_logs",
                    (
                        "Run a bounded log query for an incident window. "
                        "Excludes deploys."
                    ),
                    examples=[
                        "Find 5xx traces for checkout-web in the last 30 minutes.",
                    ],
                    tags=["search"],
                ),
            ],
        ),
        "chaos_experiments": profile(
            summary="Runs approved chaos experiments in staging only.",
            description=(
                f"{_BOILER} Fault injection in staging. Explicitly does not run "
                "chaos against production."
            ),
            tags=["chaos", "staging"],
            skills=[
                skill(
                    "run_staging_chaos",
                    (
                        "Run an approved chaos experiment in staging. Does not "
                        "target production. Does not claim production resilience "
                        "testing."
                    ),
                    examples=[
                        "Kill one staging Redis replica under experiment CHS-12.",
                    ],
                    tags=["fault-injection"],
                ),
            ],
        ),
        "runbook_author": profile(
            summary="Authors operational runbooks from incident learnings.",
            description=(f"{_BOILER} Writes runbooks. Does not execute deploys."),
            tags=["docs", "ops"],
            skills=[
                skill(
                    "write_runbook",
                    (
                        "Draft a runbook for a recurring failure mode. Excludes "
                        "live remediations."
                    ),
                    examples=[
                        "Write a runbook for checkout 5xx after bad deploys.",
                    ],
                    tags=["runbook"],
                ),
            ],
        ),
        "access_reviews": profile(
            summary="Runs quarterly access reviews for production systems.",
            description=(
                f"{_BOILER} Reviews who can deploy or read secrets. Does not "
                "perform the deploy itself."
            ),
            tags=["iam", "compliance"],
            skills=[
                skill(
                    "review_access",
                    (
                        "Produce an access-review diff for a system. Excludes "
                        "rolling out code."
                    ),
                    examples=[
                        "Quarterly review of who can kubectl in prod.",
                    ],
                    tags=["review"],
                ),
            ],
        ),
        "ops_generalist": profile(
            summary="General platform helper for deploys, flags, DNS, and CI.",
            description=(
                f"{_BOILER} Broad ops generalist that will attempt almost any "
                "platform task. Prefer specialists when staging versus "
                "production boundaries matter."
            ),
            tags=["ops", "generalist"],
            skills=[
                skill(
                    "help_with_ops",
                    (
                        "Intake ops requests and attempt a generic fix. Weak "
                        "on strict staging/production separation."
                    ),
                    examples=[
                        "Something is wrong with checkout; please fix deploy.",
                    ],
                    tags=["intake"],
                ),
            ],
        ),
        "misleading_prod_buddy": profile(
            summary="Friendly deploy helper that sounds production-ready.",
            description=(
                f"{_BOILER} Broad marketing-style Profile that mentions "
                "production often but only has permission to comment on "
                "pull requests. Does not deploy to staging or production. "
                "Negated capability: cannot roll out images despite the tone."
            ),
            tags=["ops", "misleading"],
            skills=[
                skill(
                    "comment_on_deploy_pr",
                    (
                        "Leave review comments on deploy PRs. Explicitly cannot "
                        "deploy to staging or production clusters."
                    ),
                    examples=[
                        "Comment on the checklist in PR #4412.",
                    ],
                    tags=["review-only"],
                ),
            ],
        ),
        "network_acl": profile(
            summary="Updates network ACLs and security groups.",
            description=(
                f"{_BOILER} Firewall and security-group changes. Does not "
                "deploy application images."
            ),
            tags=["network", "security"],
            skills=[
                skill(
                    "update_acl",
                    (
                        "Open or close a network path with dual control. "
                        "Excludes service rollouts."
                    ),
                    examples=[
                        "Allow staging payments-api to reach staging Redis.",
                    ],
                    tags=["acl"],
                ),
            ],
        ),
        "backup_restore": profile(
            summary="Restores datastores from backups in declared environments.",
            description=(
                f"{_BOILER} Point-in-time restores. Requires environment name "
                "and backup id. Does not deploy app images."
            ),
            tags=["backup", "data"],
            skills=[
                skill(
                    "restore_backup",
                    (
                        "Restore a named backup into a target environment. "
                        "Excludes application deploys."
                    ),
                    examples=[
                        "Restore staging orders DB to snapshot snap-99.",
                    ],
                    tags=["restore"],
                ),
            ],
        ),
        # Late-capability specialist: distinguishing skill is the last of many.
        "edge_config_late": profile(
            summary="Platform utility Agent with many routine ops Skills.",
            description=(
                f"{_BOILER} Routine helper with several ordinary Skills. The "
                "capability that matters for some needs—authoritative edge "
                "routing config for canary weight—appears only in the final "
                "Skill below. Prefer this Agent when the need is specifically "
                "edge canary weight changes, not a cluster image deploy."
            ),
            tags=["ops", "edge", "utility"],
            skills=[
                skill(
                    "list_open_changes",
                    "List open change tickets in the ops tracker.",
                    examples=["Show open CHG tickets for checkout."],
                    tags=["tickets"],
                ),
                skill(
                    "ping_oncall",
                    "Page the current primary on-call for a service.",
                    examples=["Ping checkout primary about a slow canary."],
                    tags=["oncall"],
                ),
                skill(
                    "fetch_service_owners",
                    "Return CODEOWNERS for a repository path.",
                    examples=["Who owns services/checkout-web?"],
                    tags=["owners"],
                ),
                skill(
                    "summarize_status_page",
                    "Summarize the public status page for the last day.",
                    examples=["Any active incidents on the status page?"],
                    tags=["status"],
                ),
                skill(
                    "link_runbooks",
                    "Return links to runbooks matching a keyword.",
                    examples=["Find runbooks mentioning canary."],
                    tags=["docs"],
                ),
                skill(
                    "set_edge_canary_weight",
                    (
                        "Set the edge canary traffic weight for a named "
                        "service hostname. Required context: hostname and "
                        "weight 0-100. Expected outcome: updated edge config. "
                        "This is the distinguishing capability; earlier Skills "
                        "are routine utilities. Does not deploy container "
                        "images to staging or production clusters."
                    ),
                    examples=[
                        "Set canary weight for checkout.example.com to 10%.",
                        "Shift edge canary for api.example.com from 5% to 0%.",
                    ],
                    tags=["edge", "canary-weight"],
                ),
            ],
        ),
    },
)
