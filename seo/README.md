# seo

Files to publish at the dirtClaude.ai site root.

- `robots.txt` keeps `/api/` and `/sitemap-admin/` closed and leaves the answer bots allowed.
- `llms.txt` lists only URLs that are live today. Guide and layer URLs stay off this list until those pages exist.
- `pages.csv` is the source for `llms.txt`.

```bash
python3 python/claimline/llms_txt.py seo/pages.csv --name dirtClaude --about "AI mineral prospectivity maps for BLM claims, historical mines, and public land." -o seo/llms.txt
```
