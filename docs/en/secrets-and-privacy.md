# Secrets and Privacy

> 🌐 [中文](../10-密钥与隐私.md) | **English**

This document records this repository's secret/privacy handling rules, **a leak that occurred and has been handled**,
and the long-term protections (guard tests).

> **Conclusion first**: the leak was fully handled on 2026-09-30 — carrier file deleted, working tree cleaned,
> git history rewritten and force-pushed, and **the credential itself revoked**; all four steps are done,
> and `backend/tests/unit/test_no_secrets_in_repo.py` guards against recurrence in the gate.
> The full record is kept below for reference if similar problems come up later.

---

## 1. Rules

1. Secrets go only into `.env` and the deployment environment. `backend/.env` is ignored by `.gitignore`;
   `.env.example` contains placeholders only.
2. Secrets never enter commits, never enter logs, never enter conversation records or issues.
3. When adding a new configuration item, first confirm it will not be written into a version-controlled file.
4. When an example value is needed, use an obvious placeholder such as `your_xxx_here`; do not use a truncated real value.

---

## 2. Leaks That Have Occurred (Not Fully Eliminated)

### 2.1 Hard-Coded DeepSeek API Key

**Event**: `backend/scripts/utils/init_project.py` once hard-coded a real DeepSeek API key
(`sk-d655427b…`; only the prefix is kept here for searching). The file landed in the initial commit `b8f2842`
and was later changed in `e55bf84` ("security: 移除硬编码的API Key").

**The mistake at the time**: `e55bf84` only changed the file content and **did not rewrite history**, so the key
remained in git history in full for a long time, and anyone could recover it with `git log -p`. The repository is public.

**Current state**: two things were done on 2026-09-30 — the history was rewritten and force-pushed to the public
repository, and **the credential itself was revoked**. Scanning a fresh clone from the remote no longer turns up
this string. Neither step can be omitted: the rewrite makes the string disappear from the repository, and the
revocation makes it worthless.

### 2.2 Personal Contact Information

The same stretch of history also contained the personal information below. **These values in file content were erased
along with the history rewrite** (they are now replaced with `noreply@example.com` / `REDACTED`).

**This document does not reproduce the full values** — first, there is no need; second, `test_no_secrets_in_repo.py`
scans every version-controlled file, so this document itself must stay clean:

| Content | Masked form | Where it appeared |
|------|----------|--------------|
| Personal Gmail | `JasonB…@gmail.com` | Contact block in `README.md` / `README_EN.md` |
| QQ email | `3310…@qq.com` | Same as above |
| QQ number | `3310…` | Same as above |

Also, **the author/committer email of every commit is that Gmail**.
This kind of metadata cannot be handled by `--replace-text`; use `--mail-map` instead (see the next section).

If you need the full values, retrieve them from history yourself (this command only prints; it writes nothing to any file):

```bash
git log --all -p | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' | sort -u
git log --all --format='%ae %ce' | sort -u
```

### Completed

- [x] Deleted the carrier file `backend/scripts/utils/init_project.py`.
      The file met three deletion criteria at once: it was referenced nowhere, it had a syntax error and could not be imported, and
      it was the carrier of the leak above.
- [x] Removed the personal email and QQ number from `README.md` / `README_EN.md`, redirecting to GitHub Issues instead.
- [x] Confirmed that the working tree and `HEAD` contain no key-shaped strings, no personal email and no QQ number.
- [x] Confirmed `backend/.env` is not tracked by git (`.gitignore` line 17).
- [x] This document no longer reproduces the complete key value; only the 8-character prefix is kept for searching.
- [x] **Rewrote git history and force-pushed** (executed 2026-09-30). Used `git filter-repo
      --replace-text` to erase the key and personal contact details; both `main` and `v1.0.0` have been force-updated.
      The verification method is to scan again after a **fresh clone** from the remote:

      | Check | Result |
      |--------|------|
      | Full key (`sk-` + 20 or more characters) | 0 |
      | QQ number / QQ email | 0 |
      | Personal email in file content | 0 |
      | Commit count | 71 (all preserved) |
      | Author/committer email | Still `jasonbuildai@gmail.com` (kept by your choice) |

- [x] **Revoked that DeepSeek key** (2026-09-30, done by the repository owner in the DeepSeek console).
      This is the **only step that truly removes the risk**: rewriting history only keeps it out of the repository,
      but it had already been public — it may have been crawled, forked or indexed, and GitHub may keep serving
      unreachable objects under the old SHA for some time. A string disappearing does not mean the credential is invalid; revocation does.
- [x] **Rewrote git history and force-pushed** (executed 2026-09-30). Used `git filter-repo
      --replace-text` to erase the key and personal contact details; both `main` and `v1.0.0` have been force-updated.
      The verification method is to scan again after a **fresh clone** from the remote:

      | Check | Result |
      |--------|------|
      | Full key (`sk-` + 20 or more characters) | 0 |
      | QQ number / QQ email | 0 |
      | Personal email in file content | 0 |
      | Commit count | All preserved |
      | Author/committer email | Still `jasonbuildai@gmail.com` (kept by the owner's choice) |

### At This Point, This Leak Has Been Fully Handled

The working tree, `HEAD` and the remote history — all three layers — have been confirmed clean, and the credential itself has been revoked.
The remaining items below **do not affect security**; they are optional cleanup:

- [ ] **Delete the local backup `D:\Temp\goldmind-git-backup`** (a full copy of `.git` from before the rewrite).
      It still contains the complete key — but the key has been revoked, so keeping it is no longer a risk, just unnecessary.
      The rewrite has been verified and pushed, and its rollback value is now zero, so it can be deleted.
- [ ] If you later want to change the **author email** too (this time it was kept by the owner's choice):
      `git log --format='%ae'` shows it in the metadata of every commit; it is no longer in any file content.
      A separate rewrite with `--mail-map` is needed (it will change all SHAs again).

> **Ordering reminder (for future me)**: revocation always takes priority over rewriting.
> Rewriting without revoking = the leak remains, just harder to find.

> ⚠️ **Ordering reminder**: revocation always takes priority over rewriting. Rewriting without revoking = the leak remains, just harder to find.

---

## 3. Standard Steps for Rewriting History

> This section records a process that **has been executed**, kept for future reference.
> Actually executed on 2026-09-30: `main` changed from `60e25c6` to `fefbfb1`,
> and `v1.0.0` from `9d5e522` to `df34183`; both were force-updated in the public repository.

> Back up before executing; after executing you need to force-push, and every collaborator's local clone becomes invalid.
>
> **Note**: `git filter-repo --all` rewrites **all** refs together, including the backup branch you just created.
> So the backup must be a full `.git` copy outside the repository, not a branch inside it —
> otherwise the backup gets scrubbed along with everything else, which is as good as having no safety net.

```bash
# 0. First leave a rollback backup branch
git branch backup/pre-secret-scrub

# 1. Erase the strings from history (the key and personal contact details)
#    Requires git-filter-repo: pip install git-filter-repo
#
#    All three placeholders must be replaced with the real values. How to obtain them (these two commands only print; they write no files):
#      git log -p b8f2842 -- backend/scripts/utils/init_project.py | grep -o 'sk-[A-Za-z0-9]*'
#      git log --all -p | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' | sort -u
#      git log --all -p | grep -oE '\b1[0-9]{9}\b' | sort -u        # QQ number
cat > /tmp/scrub.txt <<'EOF'
<LEAKED_KEY>==>REDACTED
<PERSONAL_GMAIL>==>noreply@example.com
<PERSONAL_QQ_EMAIL>==>noreply@example.com
<PERSONAL_QQ_NUMBER>==>REDACTED
EOF
git filter-repo --replace-text /tmp/scrub.txt

# 1b. The author/committer email is also in every commit's metadata; --replace-text cannot handle it,
#     so change it separately with --mail-map:
git log --all --format='%ae' | sort -u    # first see what is there
cat > /tmp/mailmap.txt <<'EOF'
<PERSONAL_GMAIL> <PERSONAL_GMAIL> <noreply@users.noreply.github.com>
EOF
git filter-repo --mail-map /tmp/mailmap.txt

# Or use the built-in filter-branch (slow, and officially discouraged)
# git filter-branch --force --index-filter \
#   "git rm --cached --ignore-unmatch backend/scripts/utils/init_project.py" \
#   --prune-empty --tag-name-filter cat -- --all

# 2. Clean up the reflog and unreachable objects
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 3. Verify that history no longer turns anything up (the prefix is for searching; it is not a usable credential in itself)
git log -p --all | grep -c 'sk-d655427b'              # expect 0
git log --all --format='%ae %ce' | sort -u            # expect not to see the personal email
git log --all -p | grep -cE '[A-Za-z0-9._%+-]+@(gmail|qq)\.com'   # expect 0

# 4. Push (this rewrites remote history; coordinate with all collaborators)
git push --force-with-lease origin main
git push --force-with-lease origin --tags
```

**Notes**:
- The `v1.0.0` tag also points to the old history; before force-pushing tags, confirm whether that version should be kept.
- `git filter-repo` removes the `origin` remote configuration by default; re-add it with `git remote add` before pushing.
- The `sk-d655427b` used in step 3 above is the 8-character prefix — safe to use for searching.
- After the history is cleaned, `backend/tests/unit/test_no_secrets_in_repo.py` automatically guards the working tree,
  but it **cannot see history**; history can only be handled by the steps above.

---

## 4. Credentials Currently in Effect

| Purpose | Location | Description |
|------|------|------|
| LLM (reasoning + web search) | `MIMO_API_KEY` in `backend/.env` | Xiaomi MiMo. **Note the usage compliance risk**; see Section 4, item 2 of `docs/00-产品方向.md`. |

`backend/.env` is not under version control. Under no circumstances paste its contents into commits, logs or issues.
