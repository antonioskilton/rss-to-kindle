# rss-to-kindle

A small GitHub Actions project that turns selected RSS/Atom feeds into Kindle-friendly EPUBs.

## Outputs

Each run can create up to two EPUBs:

- **AI** — engineering and AI feeds, including the filtered Nate Silver AI feed.
- **TPM** — product and technical program management feeds.

Each EPUB contains a visible linked contents page, native EPUB navigation grouped by publication, full article content when available, and links back to the original posts.

## Daily delivery

The production workflow runs at **4:30 AM America/Los_Angeles** every day.

It searches the previous seven days but excludes article IDs already recorded in `state/kindle.json`. This makes missed runs recoverable without sending the same article again.

The first live run therefore acts as a **seven-day catch-up**. Subsequent runs normally contain only articles that have appeared since the previous successful delivery.

If a section has no new articles, no EPUB is created for that section.

## Kindle email setup

The workflow expects three GitHub Actions repository secrets:

- `SMTP_USERNAME` — Gmail address used to send the documents.
- `SMTP_APP_PASSWORD` — Google App Password for that Gmail account.
- `KINDLE_EMAIL` — Amazon Send-to-Kindle email address.

The Gmail address must also be present in Amazon's Approved Personal Document E-mail List.

No password or Kindle address is committed to this public repository.

## Safe testing

Pushes to the `kindle-digest` branch build EPUBs and upload them as GitHub Actions artifacts, but **do not email anything**.

A manual workflow run has a `send_to_kindle` switch. Leave it off to test generation only. Turn it on to perform a real delivery after repository secrets are configured.

Scheduled delivery runs only from the repository's default branch, so the daily 4:30 AM delivery becomes active after this work is merged to `main`.

## Feed configuration

Edit `feeds.yaml` to add, remove, or move feeds between sections.

`filter_nate.py` independently refreshes `nate-ai.xml`, which is consumed by the AI digest.
