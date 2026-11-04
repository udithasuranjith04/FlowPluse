# Publish FlowPulse AI to GitHub

This document applies to the **current FlowPulse Café** project. An older RoadPulse remote may already be configured locally; never overwrite or force-push that history blindly.

## 1. Verify and protect the existing project

From your FlowPulse project root on the Mac:

```sh
python3 scripts/release_prep.py
# Optional: move patch .orig/.rej backups and review manifests out of the tree
python3 scripts/release_prep.py --quarantine
make lint && make test && make build
git status --short
git branch --show-current
git remote -v
```

- Fix all failing checks. Stop if preflight reports tracked sensitive files.
- Inspect `git status`, `git diff`, staged files and `.gitignore` before publishing.
- No real model accuracy claim is allowed until tested on a manually annotated, authorized sample; see [evaluation](FLOWPULSE_EVALUATION.md).
- Do not publish `.env`, credentials, tokens, runtime databases, weights, uploaded footage, screenshots showing personal accounts, or material you do not have reuse permission for. If a secret was **ever** committed, adding `.gitignore` is not enough: rotate it and clean history before making the repository public.

## 2. Create a public GitHub repository

Use [GitHub's repository creation page](https://github.com/new). Suggested repository name: `flowpulse-ai`. Choose **Public** and leave generated README, license and `.gitignore` options unchecked, because local copies exist.

## 3. Preserve existing Git history

```sh
# Run git init only if you see: fatal: not a git repository
git init -b main

# If an origin is already set, inspect it and do NOT blindly run this command.
git remote add origin https://github.com/YOUR_USERNAME/flowpulse-ai.git

git status --short
git add .
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
```

Review all staged paths. If anything private or generated is staged, **unstage it** (`git restore --staged PATH`) and fix ignore rules before continuing. If `git init`/`git remote add` was unnecessary, omit it. Do not force-push.

```sh
git commit -m "chore: prepare FlowPulse AI portfolio release"
git push -u origin HEAD
```

If the target GitHub repository already has commits, fetch and reconcile its history first. GitHub authentication is handled using your own credentials or `gh auth login`; never paste a personal access token into a source file or chat transcript.

## 4. Release v1.0.0 after Mac acceptance

Only after the local Mac checks, OBS preview/restart testing and permitted-data validation are completed: go to **GitHub → repository → Releases → Draft a new release**. Create tag `v1.0.0`, attach **no private raw videos, model weights, or local database files**, and describe it as a **portfolio prototype**. Include tested platform, verification results, known limitations, demo link, and third-party licensing notices. The tag and release are not created by these instructions.

If field accuracy has not been evaluated, disclose that limitation explicitly, rather than stating a fabricated percentage.
