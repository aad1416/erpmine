# ds_blog_posts

## Purpose
The content marketing engine. It serves as the central repository for articles, company news, and technical guides, allowing each branch office to maintain an editorial "Voice" for their specific customers.

---

## Retrieve This Table When The User Asks About

**Articles and news content**
Marketing updates or portal messages. Retrieving all live (active and non-draft) blog posts for a store’s public homepage.

**Editorial workflow and scheduling**
Finding active drafts waiting for publication. Checking the public publish date vs. the physical creation date.

**Authorship and teasers**
Retrieving the display name of the author (byline) and teaser text (summary) for listing pages. Auditing the actual body content of an article.

---

## Co-Retrieved Sibling Tables
- `ds_blog_posts_categories` — the tags linking posts to product families.
- `stores` — the branch owning the editorial voice.
