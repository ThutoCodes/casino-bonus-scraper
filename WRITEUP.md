# Write-up

## Taking this to production (200 casinos, updated daily)

**Where it runs:** A single small VPS on Hetzner Cloud (2 vCPU, 4 GB RAM, about €5 a month), with the scraper running as a Docker container. 200 pages a day, with a polite 3 second delay between requests, is around 10 minutes of work. That doesn't need serverless or Kubernetes. A VPS is cheap, easy to debug, and gives a fixed IP if a source ever asks to whitelist us.

**Database and backups:** Postgres, with a `casinos` table and an append-only `bonus_snapshots` table. Each daily run adds one row per casino with the extracted fields, the raw terms and the model used. That gives a history of bonus changes and lets me re-run extraction on old text if the prompt improves. I would use a managed Postgres (DigitalOcean, about $15 a month) for daily backups and point-in-time recovery. On top of that, a nightly `pg_dump` goes to Backblaze B2, kept for 30 days, so backups don't depend on one provider. I would test a restore once, because an untested backup isn't a backup.

**Domain, DNS and HTTPS:** The domain is registered with Cloudflare, and its DNS also runs on Cloudflare, which handles HTTPS and caching at the edge. On the server, Caddy acts as the reverse proxy and renews Let's Encrypt certificates automatically.

**Scheduling and failure alerts:** A systemd timer runs the scraper once a day. The script already exits with an error if any casino fails. At the end of each successful run it pings Healthchecks.io, which alerts me by email if the ping doesn't arrive, so I also find out when the job didn't run at all. I would also alert if more than about 5% of casinos fail, or if many suddenly come back as "needs review", which usually means a source changed its HTML. To save cost, the LLM is only called when a casino's terms text has changed since yesterday.

**Rough monthly cost:** VPS €5, database $15, backups under $1, LLM about $1 (a small Flash-Lite model on mostly unchanged terms), domain about $1, monitoring free. Roughly $25 a month.

## AI

I used Claude Code (Claude Opus 5.5) to build and deploy the scraper; the scraper uses Gemini 3.5 Flash-Lite to turn bonus terms into fields.<br>
For 36Vegas, a spins-only offer, Gemini returned 0x wagering because the page also lists "bonus money 0x" next to "bonus spins 2x".<br>
The scraper's check that each number appears in the source text passed it, because "0x" really is on the page.<br>
It was only caught by comparing the JSON with the raw terms by hand.<br>
I changed the prompt to use the wagering for what the offer actually gives, and the README notes that this check can't catch a number that is in the text but wrong.

## Time taken

About 40 minutes.

## What's missing

- The casino list is fixed at 3; there is no discovery from Bojoko's sitemap.
- There is no scheduled daily run yet; the page updates when the script is run and pushed.
- The number check confirms each value appears in the source text, but not that it is the right one.
