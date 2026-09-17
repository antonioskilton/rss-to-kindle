# rss-to-kindle

Small, deterministic RSS transformations that can be consumed by NetNewsWire or later reused for Kindle delivery.

## Nate Silver — AI+

`filter_nate.py` reads Nate Silver's official RSS feed and keeps only articles that also appear on his **AI+** tag page.

The GitHub Action refreshes the filtered feed every four hours and commits it to `nate-ai.xml` when the contents change.

Feed URL:

`https://raw.githubusercontent.com/antonioskilton/rss-to-kindle/main/nate-ai.xml`
