# Travel Inn v1 — What I Need Before / During Build

**From:** Priyanshu
**Date:** 17 Aug 2026
**Status:** Data audit complete. Stack decided. Waiting on the three blockers below to start.

---

## Blocking — needed before I create anything

### 1. Data residency — does the data have to stay in India?

**Why it blocks:** the database region is fixed when the project is created and cannot be changed afterwards. If this is confirmed after we build, it means rebuilding rather than changing a setting.

**Who has it:** Sukanya, or whoever handles their compliance. It was question 19 in the original scoping document and was never answered.

**What I need:** a yes or no. If yes, I create in an India region on day one and nothing else changes.

---

### 2. What is in scope for version 1?

**Why it blocks:** the August scoping document defined a pilot on the Hotels / Property Updates folder — 52 files, 49 properties. Since then they have sent a 186-question bank that includes safari zones, national park features, festival dates and source-market feedback. **None of that exists in the pilot data**, and most of it cannot come from property sheets at all.

**What I need to know:** is v1 still the 52-file Property Updates set, or has the scope grown? If they expect all 186 questions answered, expectations have drifted a long way from what was scoped and priced.

---

### 3. Is the 186-question bank the acceptance test?

**Why it blocks:** it decides what "pass" means. Sukanya and Gaurav committed to 15–20 test questions by 18 August. We received 186 instead.

**What I need:** either confirmation that the 186 bank replaces the 15–20, or the curated shortlist. If it is the 186, we should agree upfront which subset is the actual bar — I have already mapped the 30 strongest, with the exact file and section that proves each one.

---

## Needed soon — not blocking, but wanted early

### 4. Was the proposal sent, and what was agreed?

I do not know the final number or what scope it covers. Useful for knowing where the line is when things get added mid-build.

### 5. Whose accounts carry the AI usage cost?

Anthropic and Gemini API keys. Either ours and billed through, or theirs created upfront so we test on their keys and there is no surprise invoice. At full scale this is the main running expense.

### 6. Was the data gap raised with them?

Two things the audit found that they should know about before testing starts:
- **No star ratings exist anywhere in the data** — despite Ravi naming this as the primary quoting parameter
- **Pool and spa are stated inconsistently** — five different forms across the corpus

If they add a small structured amenities block to their template (star/category, pool, spa, Wi-Fi, AC as explicit yes/no), roughly 15 currently-failing questions become answerable. Their own 2024 template already did this with icons; the current one dropped it.

### 7. Who are the testers, and who signs off?

Nazim is confirmed. Who else, how many, and who formally says the pilot has passed.

---

## Nice to have

### 8. Where does it live?

A `travelinn.in` subdomain, or a URL we provide? Only needs a DNS record from them, and only at the end.

### 9. Login for v1

Shared password was agreed for the pilot. Confirming that still holds — or whether they now expect Microsoft SSO, since they are an M365 shop.

### 10. What is Facile Blu?

Mentioned in the first meeting as a cloud tool they use internally, never explained. Out of scope for v1, but I still do not know what it does or whether it holds data we will eventually need.

---

## For later — phase 2 only, but slow to obtain

### 11. SharePoint access

Auto-sync will need an app registration inside their Microsoft 365 tenant with admin consent. **This is the one thing we cannot create on our side at any price.**

Two complications worth raising early:
- The data sits in **Gaurav's personal OneDrive**, not a team SharePoint site. Personal drives are awkward to grant programmatic access to, and the whole thing disappears if he leaves.
- IT approvals are slow. Worth asking now even though it is not needed until phase 2.

**What to ask:** who their M365 admin is, and whether the Product Drive can be moved to a proper team site.

### 12. File-type breakdown of the full drive

Before anyone quotes phase 2. The 500 GB is mostly photography — only the text-bearing documents need extraction, and that single number swings the phase-2 estimate by roughly 3×.
