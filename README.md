# rss-to-kindle

Small, deterministic RSS transformations that can be consumed by NetNewsWire or delivered to Kindle.

## Nate Silver — AI+

`filter_nate.py` reads Nate Silver's official RSS feed, checks each post's public Substack metadata, and keeps only posts carrying the `ai` tag.

The GitHub Action refreshes the filtered feed every four hours and commits it to `nate-ai.xml` only when the feed changes.

Feed URL:

`https://raw.githubusercontent.com/antonioskilton/rss-to-kindle/main/nate-ai.xml`

## Daily Kindle digests

The Kindle workflow builds two EPUBs from `feeds.yaml`: **AI** and **TPM**. Each EPUB contains only articles not previously delivered, grouped by publication with a clickable table of contents.

Each EPUB includes an embedded JPEG cover image so Kindle can display a library thumbnail. The cover is generated automatically with the section name, date, and article count.

Delivery runs at **4:30 AM America/Los_Angeles**. The first successful delivery used a seven-day catch-up window; future runs use the persisted article IDs in `state/kindle.json` to avoid duplicates.

Required GitHub Actions secrets:

- `SMTP_USERNAME`
- `SMTP_APP_PASSWORD`
- `KINDLE_EMAIL`

Gmail is used via SMTP with an App Password. The sender must also be present in Amazon's Approved Personal Document E-mail List.

The workflow supports manual dispatch. Set `send_to_kindle` to true only when you intentionally want a live delivery; ordinary branch pushes build and validate without sending.
