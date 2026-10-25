# Public GitHub publication and course submission

Status: **local Git repository only — not pushed, not submitted**.

No GitHub push or LMS submission was performed, as requested.

The local history contains an initial required-structure scaffold commit followed by
the implementation. The supplied `.bundle` preserves that history. The `.zip` is a
source-only distribution and does not contain Git history.

If using the Git bundle in a new location:

```bash
git clone multi-agent-dev-team.bundle multi-agent-dev-team
cd multi-agent-dev-team
```

To publish, create a new **public**, empty repository named `multi-agent-dev-team`
on your GitHub account (do not initialize it with a README). From this repository:

```bash
git status --short
# Review staged/tracked content; never add .env, runtime memories or generated logs.
git remote add origin https://github.com/YOUR-USERNAME/multi-agent-dev-team.git
git push -u origin main
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Replace `YOUR-USERNAME` with your account name. Authenticate using GitHub's normal
credential flow; never put a token in the remote URL. If you already have a suitable
public course repository, integrate this source deliberately instead of overwriting
its history or force-pushing.

After pushing, open the repository while signed out and verify public access. Compare
the full local `HEAD` SHA against the remote branch SHA. Run the Docker and live-model
checks from the README, and check the GitHub Actions result. If fixes are required,
commit and push them and submit the newest verified SHA.

Submit through the LMS:

- Repository URL: the actual public GitHub URL after publication.
- Commit SHA: the exact 40-character published commit SHA.
- Milestone: Module 1 — Coder Agent v1.0.

A local commit or ZIP is not evidence of completed GitHub/LMS submission. The delivery
manifest outside the repository records the local commit SHA without creating a
self-referential commit hash inside its own contents.
