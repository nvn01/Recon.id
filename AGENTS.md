# Recon Agent Instructions

## Project Purpose

Recon is an early-stage repository for building the easiest way to monitor wishlist computers, computer parts, and peripherals across multiple preloved marketplaces and social platforms.

The product goal is simple: users should not need to repeatedly check every marketplace by hand. Recon should discover relevant new listings quickly, normalize them into a consistent structure, and make them easy to inspect, compare, and revisit.

## Current Status

This project is still very early. Do not treat the repository as a finished app scaffold.

The current focus is scraper, backend, and database readiness. Some exploratory scraper tests already work, but the method is not yet standardized enough for reliable database ingestion.

The main work right now is:

- Make scraping repeatable, source-aware, and resilient.
- Normalize listings into a consistent data structure before writing them to the database.
- Extract useful database fields from messy post descriptions, including category, brand, price, condition, locations, status, and seller context.
- Avoid rate limits, temporary blocks, duplicate spam, and brittle scraping behavior.
- Keep the system inspectable so future agents can understand what happened during each scrape run.

UI work is intentionally deferred until real normalized listings and backend contracts exist.

## Product Freshness Goal

The long-term product goal is near minute-level freshness so users do not miss wishlist items.

Do not blindly run every connector every minute in production. Prove source safety first. Start with conservative staging checks, connector-level cooldowns, retry limits, backoff, and clear health metrics. Tighten cadence only when the source can tolerate it without lockouts, noisy failures, or duplicate pileups.

## Planning Context

Before making major changes, inspect the existing planning artifacts:

- `.plan/first-pass.html`
- Any nearby planning notes or scraper files related to the requested task.

Preserve the current architecture direction unless the user explicitly changes it:

1. Scraper and backend setup.
2. Database schema and ingestion contracts.
3. Scraper core and source connectors.
4. Backend API.
5. Operational hardening before public UI work.

## Major Feature Proposal Workflow

When Novandra opens a new branch/worktree or asks what a new major feature would look like, do not start building immediately.

First answer with a complete feature model/spec that explains:

- What the user experience should be.
- What data model or storage changes are needed.
- What API/backend behavior is needed.
- What frontend behavior is needed, if any.
- How the feature works without violating current project constraints, such as no user accounts or no authentication.
- Important tradeoffs, failure modes, abuse risks, privacy risks, and edge cases.
- How the feature should be tested and verified.
- Whether it belongs in the current plan or should update `.plan/first-pass.html`.

Example trigger:

> what would it look like if user interested in one post then want to save or like some the product in the web app without need to doing some login or authentication since our app is not have users profile feature yet.

For this kind of request, propose the whole model first. Wait for explicit approval before implementing. Approval may be phrased casually, such as "Oke i like that, build it!", "Love it, build it!", "build it", or a similar clear instruction.

If Novandra asks follow-up questions, keep refining the model/spec. Do not treat interest in the idea as permission to build.

## Private Local Skills

The `.agents/` directory is intentionally private and ignored by git. It may contain personal, sensitive, or non-public workflow knowledge.

When `.agents/` is available locally:

- Read `.agents/RECRUITED_SKILLS.md` before choosing workflow skills.
- Use only the relevant skill files for the task.
- Do not copy private skill contents into public repository files.
- Do not remove `.agents/` from `.gitignore`.
- Do not assume GitHub or another remote environment has access to `.agents/`.

When `.agents/` is not available, continue with the public repository context and explain any limitation if it affects the work.

## Skill And Agent Usage

Use specialized skills and subagents when they materially improve the work, especially for:

- Scraper design and connector investigation.
- Backend and API design.
- PostgreSQL, Prisma, and migration planning.
- TDD, verification, linting, formatting, and coverage checks.
- Security review, especially around scraping, user data, environment variables, and deployment.
- Homelab CI/CD while the project is still hosted locally.
- Product, legal, compliance, operations, business, marketing, and brand review when those perspectives are relevant.

Knowledge-work skills act like internal departments. If a non-technical department has a recommendation, warning, progress update, or decision request, leave a clear ticket-style note for Novandra instead of making the business decision silently.

For investigation-heavy work, prefer parallel research or subagents when available. Synthesize their findings into concrete decisions, risks, and next steps.

## Working Style

Be direct, critical, and truthful. If a decision, algorithm, tool, or architecture choice is weak, say so and propose a better option.

Do not flatter the plan. Recon needs practical scrutiny, especially around scraping reliability, source limits, legal exposure, operational cost, and data quality.

When implementation begins:

- Prefer test-driven changes for new behavior and bug fixes.
- Keep changes scoped to the requested area.
- Validate inputs at boundaries.
- Avoid hardcoded secrets.
- Run the relevant tests, type checks, lint, formatting, and security checks when available.
- Review the final diff for risky patterns before handing off.

## Scraping Rules

The scraper must be designed as a reliable ingestion system, not a quick one-off script.

Required expectations:

- Use public data only unless the user explicitly approves another authenticated workflow.
- Respect source-specific limits, errors, and blocking signals.
- Implement per-source backoff, cooldowns, retry limits, and failure logging.
- Make each connector idempotent so repeated runs do not create duplicate listings.
- Store source URL, external listing identity when available, scrape timestamp, raw text, and parsed database fields.
- Preserve raw descriptions when extracting category, brand, condition, location, or price from unstructured text.
- Mark inferred fields as inferred. Do not present low-confidence extraction as fact.
- Prefer structured parsing when a source provides structured data.
- Keep connector-specific logic isolated behind a shared normalized listing contract.

VPN or proxy-capable egress may be useful later, but do not use network switching to hide broken scraper behavior. Fix cadence, parsing, backoff, and connector health first.

## Data Contract Direction

Normalized listings should be able to represent at least:

- Source platform and source URL.
- External listing ID or stable derived fingerprint.
- Title.
- Description or raw post text.
- Price and currency.
- Product category.
- Brand.
- Condition.
- One or more public listing locations.
- Seller or account identity when available.
- Original image URLs and cached thumbnail metadata.
- Listing status, such as active, sold, removed, unknown, or duplicate.
- First fetched, last fetched, and scraper-side run metadata.
- Parser provenance in scraper-side logs or notes until the database plan explicitly adds provenance columns.

Design the schema so future agents can inspect why a field has a value.

## Inspectability

Every runtime feature should be inspectable by another agent or future session.

For scraper and backend work, include or preserve:

- Scrape-run logs.
- Connector health state.
- Source-specific error categories.
- Dedupe decisions.
- Ingestion counts.
- Raw-to-normalized mapping evidence.
- Clear environment variable names.
- Minimal runbooks or comments where operational behavior is not obvious.

## Section Overrides

Some folders, services, features, or platform connectors may have their own `AGENTS.override.md`.

Use those files for local context such as:

- Platform-specific scraping notes.
- Footnotes and issue history.
- Known brittle selectors or parsing assumptions.
- Connector health findings.
- Operational cautions for future agents.

When working inside a folder with an override file, read it together with this root file. The more specific override controls local details, but it should not contradict the root project direction without explaining why.

After building a major feature, create or update the right local agent context file when the implementation leaves durable assumptions, feature-specific behavior, or operational risks that future agents need to understand.

Use these naming rules:

- `AGENTS.override.md` for broad folder-level context that applies to everything in that directory.
- `AGENTS.<area>.md` for a specific major feature or subsystem inside a busy directory, such as `AGENTS.api.md`, `AGENTS.save-feature.md`, `AGENTS.parser.md`, or `AGENTS.thumbnail-cache.md`.

Do not create context files for trivial edits. Create them when they explain decisions that would otherwise be rediscovered later, such as API contracts, data parsing assumptions, anonymous-user behavior, storage rules, rate-limit behavior, or known failure modes.

## Deployment Direction

Use the homelab CI/CD path for now. Keep the architecture portable so Recon can move to a VPS or another hosting platform after the app and scraper are stable.

Prefer Dockerized services for the web app, scraper, and PostgreSQL. Keep staging and production configuration separate, and never commit real secrets.

## Documentation And Handoff

Capture durable project knowledge in the right place:

- Architecture, schema, API, scraper, or deployment decisions belong in project docs or nearby override files.
- Temporary debugging notes should stay local unless they are useful to future contributors.
- Private skill knowledge stays private.
- If there is no obvious documentation location, ask before creating a new top-level file.

When leaving a handoff, include:

- What changed.
- What was verified.
- What remains risky or unknown.
- Which files or commands matter next.
