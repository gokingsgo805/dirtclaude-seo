# Claimline Python kit

Same SEO and answer-engine checks as the Claimline desk. Python 3.9 or newer. Standard library only.

```bash
python3 python/claimline/selftest.py
python3 python/claimline/audit.py https://dirtclaude.ai --brand dirtClaude
python3 python/claimline/audit.py --html page.html --format md --fail-under 70
python3 python/claimline/brief.py --question "What does dirtClaude show for a BLM claim?" --brand dirtClaude --draft-file notes.txt
python3 python/claimline/llms_txt.py python/claimline/fixtures/pages.csv --name dirtClaude
python3 python/claimline/faq_schema.py python/claimline/fixtures/faqs.txt
```

`audit.py` exits 2 on fetch errors. With `--fail-under N` it exits 1 when the overall score is below N, so a guide can gate CI.

The audit will not fetch loopback, link-local, or private addresses. URL checks also read `/robots.txt`, `/llms.txt`, and `/sitemap.xml`.
