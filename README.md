# RSS to Kindle

[![Kindle RSS delivery](https://github.com/antonioskilton/rss-to-kindle/actions/workflows/build-kindle-digests.yml/badge.svg)](https://github.com/antonioskilton/rss-to-kindle/actions/workflows/build-kindle-digests.yml)

A small, serverless reading pipeline that turns selected RSS feeds into clean daily EPUBs and delivers them to Kindle automatically.

**Live project showcase:** https://antonioskilton.github.io/rss-to-kindle/

## What it does

Every morning at **4:30 AM America/Los_Angeles**, GitHub Actions:

1. Reads the RSS/Atom feeds configured in `feeds.yaml`.
2. Finds recent articles that have not already been delivered.
3. Uses full feed content when available, otherwise fetches and extracts the public article page.
4. Cleans the article HTML into Kindle-friendly markup.
5. Groups new articles into two daily editions: **AI** and **TPM**.
6. Builds EPUBs with generated covers, a visible contents page, and native EPUB navigation.
7. Emails the EPUBs to Amazon Send to Kindle through Gmail SMTP.
8. Records successfully delivered article IDs in `state/kindle.json` so they are not sent again.

If a section has no new articles, no EPUB is created for that section.

```text
RSS / Atom feeds
      ↓
GitHub Actions
      ↓
extract + clean + deduplicate
      ↓
   ┌───────┬───────┐
   │ AI    │ TPM   │
   │ .epub │ .epub │
   └───────┴───────┘
      ↓
Gmail SMTP
      ↓
Send to Kindle
```

## The EPUBs

Each edition is designed to feel more like a small morning reader than an RSS export.

- Generated **1200×1600 cover image** with section, date, and article count
- Visible contents page grouped by publication
- Native EPUB table of contents for Kindle navigation
- Clean article typography with headings, lists, links, code, and emphasis preserved
- Publication and publication date shown on each article
- Link back to the original article
- Link back to the contents page
- No summaries, ranking, or recommendation layer

The source articles themselves are not published by this repository or the GitHub Pages site.

## Why GitHub Actions?

The entire application runs without a conventional backend.

GitHub provides the code host, scheduler, execution environment, logs, artifact storage, secret management, and persistent delivery state. There is no VPS, database, long-running process, or paid automation service to maintain.

That makes the repository itself the application.

## Configuration

### Feeds

Edit `feeds.yaml` to add, remove, or reorganize sources. Feeds are grouped into sections, which become separate EPUBs.

Current sections:

- **AI** — AI, software engineering, and related writing
- **TPM** — technical program management, product, and organizational thinking

### Delivery secrets

The Kindle workflow expects these GitHub Actions secrets:

- `SMTP_USERNAME` — Gmail address used to send the documents
- `SMTP_APP_PASSWORD` — Google App Password for SMTP authentication
- `KINDLE_EMAIL` — the destination Send to Kindle address

The Gmail sender must also be present in Amazon's **Approved Personal Document E-mail List**.

Secrets are never committed to the repository.

## Running it

### Scheduled delivery

The workflow in `.github/workflows/build-kindle-digests.yml` runs every day at **4:30 AM Pacific time**.

### Manual build or delivery

The same workflow supports `workflow_dispatch` from GitHub Actions.

- Leave `send_to_kindle` **false** to build and inspect the EPUB artifacts without sending them.
- Set `send_to_kindle` **true** only when you intentionally want a live Kindle delivery.
- `lookback_hours` controls how far back the collector searches; previously delivered article IDs are still excluded.

Generated EPUBs and the build manifest are uploaded as short-lived workflow artifacts for inspection.

## Delivery state and deduplication

`state/kindle.json` stores the IDs of articles that were successfully delivered. Article IDs are derived from canonicalized URLs, with common tracking parameters removed first.

Delivery state is updated only after the SMTP delivery step succeeds. This means normal reruns do not resend articles that have already been recorded.

## Nate Silver AI feed

The repository also maintains a filtered RSS feed for Nate Silver.

`filter_nate.py` reads his official feed, checks each post's public Substack metadata, and retains posts carrying the `ai` tag. `.github/workflows/update-nate-ai.yml` refreshes the result every four hours and commits `nate-ai.xml` only when it changes.

Filtered feed:

```text
https://raw.githubusercontent.com/antonioskilton/rss-to-kindle/main/nate-ai.xml
```

That filtered feed is then consumed like any other source by the Kindle pipeline.

## Project structure

```text
.github/workflows/
  build-kindle-digests.yml   Daily build + Kindle delivery
  update-nate-ai.yml         Refresh filtered Nate Silver feed
  pages.yml                  Publish the project showcase

docs/                        GitHub Pages case study
feeds.yaml                    RSS sources and section definitions
kindle_digest.py              Collect, extract, clean, and build EPUBs
deliver_kindle.py             SMTP delivery + successful-delivery state
filter_nate.py                Nate Silver AI feed filter
state/kindle.json             Persistent delivered-article IDs
nate-ai.xml                   Generated filtered RSS feed
```

## Development

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Build locally without sending anything:

```bash
python kindle_digest.py --lookback-hours 168
```

Output is written to `dist/`.

## Project story

This project was designed, implemented, tested, and deployed largely from an iPhone using ChatGPT and GitHub. GitHub Actions acts as the remote runtime: code can be changed from the phone, a workflow run performs the real build, and the resulting EPUB can be inspected or delivered without a laptop or home server.

The longer visual walkthrough is on the [GitHub Pages showcase](https://antonioskilton.github.io/rss-to-kindle/).
