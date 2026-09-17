# rss-to-kindle

Small, deterministic RSS transformations that can be consumed by NetNewsWire or later reused for Kindle delivery.

## Nate Silver — AI+

`filter_nate.py` reads Nate Silver's official RSS feed, checks each post's public Substack metadata, and keeps only posts carrying the `ai` tag.

The GitHub Action refreshes the filtered feed every four hours and commits it to `nate-ai.xml` only when the feed changes.

Feed URL:

`https://raw.githubusercontent.com/antonioskilton/rss-to-kindle/main/nate-ai.xml`
