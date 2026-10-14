# Monthly AI research digest

A Python script and GitHub Actions workflow that produce a monthly shortlist of 10 AI papers from arXiv. No Python dependencies, paid AI service, or API key is required.

## Create your GitHub repository

GitHub calls this a **repository**, rather than a folder. Suggested name: `ai-research-digest`. Private is a good default for a personal reading digest.

If using GitHub CLI, install it from https://cli.github.com/ and run these commands in this folder:

```powershell
gh auth login
gh repo create ai-research-digest --private --source . --remote origin --push
```

The folder already has a local Git repository and initial commit. Alternatively, create an empty repository at https://github.com/new, copy its URL, and run:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/ai-research-digest.git
git push -u origin main
```

Enable Issues and GitHub Actions in the repository settings. Organization policies may restrict Actions or issue creation.

## Monthly schedule and delivery

The included `.github/workflows/monthly-digest.yml` runs on the **3rd of each month at 14:17 UTC** (9:17 a.m. Chicago during daylight saving time, 8:17 a.m. during standard time). It covers the previous complete UTC calendar month. The delay gives arXiv time to index month-end papers.

Once pushed to the default branch with Actions enabled, the schedule is active automatically. For an immediate test, open **Actions → Monthly AI research digest → Run workflow**. Leave the month blank or enter `2026-09` to backfill September 2026. Reruns do not create another issue with the same monthly title; an existing digest is left as originally published.

To receive the digest, choose **Watch → Custom → Issues** (or **All activity**) on your repository, and enable email delivery in your GitHub notification settings. Issues created by the workflow should then appear through GitHub notifications. No separate SMTP credentials are needed. This publishes the digest to repository watchers; it does not send email directly.

Downloads of the Markdown and JSON digest are also available in the workflow's artifacts for 90 days. Digests are not committed automatically. Download artifacts or copy issue contents for a permanent local archive.

Change `17 14 3 * *` in the workflow to adjust the schedule: minute, hour (UTC), day of month, month, day of week. GitHub schedules can run late, only run on the default branch, and scheduled workflows in public repositories can be disabled after 60 days without repository activity. Check Actions periodically and enable workflow-failure notifications.

## Run locally

Requires Python 3.11 or newer:

```powershell
python -m unittest discover -s tests -v
python digest.py
python digest.py --month 2026-09
```

Results go to `digests/YYYY-MM.md` and `digests/YYYY-MM.json`. To publish locally, set `GITHUB_REPOSITORY` to `owner/repo` and `GITHUB_TOKEN` to a token with access to that repository and Issues write permission, then run `python digest.py --publish`. Keep tokens out of files and Git. GitHub Actions supplies its own scoped token automatically.

## Customize usefulness

Edit `config.json`. Categories default to AI, machine learning, language, vision, and statistical machine learning. The ranking emphasizes practical LLM work, agents, reasoning, evaluation, efficiency, open source, and reproducibility. Add domain-specific phrases or increase their weights to prioritize your interests.

Each keyword contributes its weight once if it appears anywhere in the title or abstract. Selection discounts previously represented keywords by half to improve topic variety. Matching is case-insensitive substring matching, so it is approximate. It is **not a scholarly measure of usefulness or quality**: no citation counts, expert review, full-paper reading, or independent evaluation are performed. The digest includes the author abstract, source links, and keyword signals rather than generated claims about results.

The script fetches up to 3,000 of the most recently submitted matching papers in the month, with pagination and delays. When matches exceed that cap, earlier papers may be excluded; the digest explicitly flags incomplete coverage. Increase `max_candidates` (up to 30,000) if needed, narrow categories, and adjust the workflow timeout for larger searches. Fetch failures and insufficient candidate counts fail the workflow instead of publishing a misleading digest. A month with unusually long abstracts may exceed GitHub's issue-body limit; local files remain available as artifacts.

## Documentation

- arXiv API: https://info.arxiv.org/help/api/user-manual.html
- GitHub schedules: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- GitHub notifications: https://docs.github.com/en/account-and-profile/managing-subscriptions-and-notifications-on-github/setting-up-notifications/configuring-notifications

## Verification status

Offline tests cover month boundaries, feed parsing, ranking diversity, duplicate publication prevention, and incomplete feed failures. A live arXiv fetch and GitHub Actions run must still be verified after network/account access is available.
