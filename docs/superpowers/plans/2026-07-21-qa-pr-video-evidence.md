# QA PR Hosted Video Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `qa-pr` so successful frontend acceptance flows are recorded, normalized, published as short-lived Snapdoc video artifacts, and rendered appropriately on GitHub, GitLab, and Bitbucket with screenshot/GIF fallback.

**Architecture:** Keep `qa-ticket` as the test-planning/execution engine and make video an outward evidence adapter owned by `qa-pr`. Use deterministic helper scripts for WebM-to-H.264 normalization and forge markup generation, while the skill controls checkpoints, secret/privacy rules, sticky-comment upsert, and fallback behavior.

**Tech Stack:** Markdown agent skill, `agent-browser`, `ffmpeg`/`ffprobe`, Snapdoc CLI JSON contract, Python 3 standard library, shell, GitHub `gh`, GitLab `glab`/REST API, Bitbucket `bt`.

## Global Constraints

- Do not begin until the Snapdoc plan at `/home/carraes/projs/snapdoc/docs/superpowers/plans/2026-07-21-first-class-video-artifacts.md` is implemented and its CLI/API JSON contract is locally verified.
- Record only a clean replay after QA passes; never record exploration, retries, bug fixing, passwords, secrets, production data, token-bearing consoles, or unrelated desktop content.
- Normalize to H.264 MP4, `yuv420p`, no audio by default, at most 1920×1080, 30fps, ten minutes, and `100000000` bytes.
- Publish a new Snapdoc artifact for every QA run with `--ttl 3d`; never update a prior run's artifact.
- Keep the existing checkpoint before the first outward PR/MR comment.
- Keep exactly one `<!-- qa-pr-evidence -->` sticky comment and update it on reruns.
- GitHub uses an HTML `<video>` plus watch fallback; GitLab uses native video Markdown plus watch fallback; Bitbucket uses a clickable poster plus watch fallback.
- Passcode-protected evidence emits only a watch link.
- If recording, conversion, poster, Snapdoc, or forge rendering fails, retain the QA verdict and fall back to screenshots/GIFs with an explicit degraded-evidence note.
- Use only localhost for application QA, preserving the existing `qa-ticket` safety rule.
- Implement test-first and make one conventional commit per task. Do not post real comments, upload real evidence, push, or publish without explicit user approval.

---

## File map

New files:

- `qa-pr/scripts/normalize-video.sh` — bounded, deterministic WebM-to-MP4/poster conversion.
- `qa-pr/scripts/render-video-evidence.py` — pure forge-specific markup renderer.
- `qa-pr/tests/test-normalize-video.sh` — synthetic-media contract test.
- `qa-pr/tests/test_render_video_evidence.py` — markup/passcode/fallback unit tests.
- `qa-pr/references/snapdoc-video-contract.md` — exact CLI JSON fields and failure semantics consumed by the skill.

Existing file:

- `qa-pr/SKILL.md` — capture, publish, checkpoint, forge detection/upsert, security, and fallback workflow.

### Task 1: Build and test the forge evidence renderer

**Files:**
- Create: `qa-pr/scripts/render-video-evidence.py`
- Create: `qa-pr/tests/test_render_video_evidence.py`
- Create: `qa-pr/references/snapdoc-video-contract.md`

**Interfaces:**
- Produces: command `render-video-evidence.py --forge <github|gitlab|bitbucket> --artifact-json <path>`.
- Consumes these Snapdoc JSON keys: `id`, `has_passcode`, `version_url`, `version_file_url`, `version_poster_url`, `expires_at`.
- Emits only the media fragment; `SKILL.md` owns the surrounding verdict table/comment.

- [ ] **Step 1: Write failing renderer tests**

Use `unittest` with a temporary artifact JSON file. Assert exact fragments:

```python
self.assertIn('<video controls preload="metadata"', github)
self.assertIn('src="https://snap/v/1/media/qa.mp4"', github)
self.assertIn('![QA recording](https://snap/v/1/media/qa.mp4)', gitlab)
self.assertIn('[![QA recording](https://snap/v/1/poster.jpg)](https://snap/v/1)', bitbucket)
self.assertIn('[▶ Open QA recording](https://snap/v/1)', output)
self.assertNotIn('version_file_url', protected_output)
self.assertNotIn('<video', protected_output)
```

Also test a missing poster on Bitbucket degrades to the watch link and an unsupported forge exits nonzero.

Run: `python3 qa-pr/tests/test_render_video_evidence.py -v`

Expected: FAIL because the renderer does not exist.

- [ ] **Step 2: Implement the renderer with the standard library**

Use `argparse`, `json`, `html.escape`, and `urllib.parse.urlparse`. Validate that every URL is HTTPS and that file URLs end in `.mp4`; never interpolate unvalidated values. Render:

```text
github   -> <video controls preload="metadata" poster="..." src="..."></video>
gitlab   -> ![QA recording](VERSION_FILE_URL)
bitbucket-> [![QA recording](VERSION_POSTER_URL)](VERSION_WATCH_URL)
```

Append `[▶ Open QA recording](VERSION_WATCH_URL) · expires EXPIRES_AT` for every forge. If `has_passcode` is true, emit only that link. If Bitbucket has no poster, emit only that link plus `_(poster unavailable)_`.

- [ ] **Step 3: Document the consumed Snapdoc contract**

In `snapdoc-video-contract.md`, include one concrete JSON object, required/optional keys, three-day TTL, passcode behavior, poster partial failure, and the rule that `qa-pr` creates a new artifact each run. State that upload credentials never enter a PR comment.

- [ ] **Step 4: Verify and commit**

Run: `python3 qa-pr/tests/test_render_video_evidence.py -v`

Expected: all tests PASS.

```bash
git add qa-pr/scripts/render-video-evidence.py qa-pr/tests/test_render_video_evidence.py qa-pr/references/snapdoc-video-contract.md
git commit -m "feat: render hosted qa video evidence"
```

### Task 2: Build and test deterministic video normalization

**Files:**
- Create: `qa-pr/scripts/normalize-video.sh`
- Create: `qa-pr/tests/test-normalize-video.sh`

**Interfaces:**
- Produces: `normalize-video.sh <input.webm> <output.mp4> <poster.jpg>`.
- Guarantees successful output is H.264, `yuv420p`, silent, at most 1080p/30fps, at most 600 seconds and `100000000` bytes.

- [ ] **Step 1: Write the failing shell contract test**

The test creates a two-second synthetic WebM in a temporary directory, invokes the normalizer, and asserts with `ffprobe` that the output video codec is `h264`, pixel format is `yuv420p`, no audio stream exists, duration is at most two-and-a-half seconds, size is below the limit, and the poster is JPEG.

```bash
ffmpeg -f lavfi -i testsrc=size=640x360:rate=30 -t 2 -c:v libvpx-vp9 "$tmp/input.webm"
qa-pr/scripts/normalize-video.sh "$tmp/input.webm" "$tmp/output.mp4" "$tmp/poster.jpg"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$tmp/output.mp4")" = h264
test "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$tmp/output.mp4")" = ""
```

Also construct a metadata-only eleven-minute input with `-t 601` at a very low frame rate and assert the script refuses it before encoding.

Run: `bash qa-pr/tests/test-normalize-video.sh`

Expected: FAIL because the normalizer does not exist.

- [ ] **Step 2: Implement preflight and primary encode**

Use `set -euo pipefail`, validate exactly three arguments, require `ffmpeg` and `ffprobe`, require a regular readable input, and create outputs through temporary sibling files renamed only after success. Reject source duration above 600 seconds.

Primary encode:

```bash
ffmpeg -y -i "$input" -map 0:v:0 -an \
  -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p \
  -vf "scale='min(1920,iw)':-2:force_original_aspect_ratio=decrease,fps=30" \
  -movflags +faststart "$tmp_mp4"
```

Generate the poster from a representative early frame:

```bash
ffmpeg -y -ss 1 -i "$tmp_mp4" -frames:v 1 -q:v 3 "$tmp_poster"
```

- [ ] **Step 3: Add bounded retry and output validation**

If the primary MP4 exceeds `100000000`, retry once at CRF 30 and maximum 1280px width. If the retry still exceeds the limit, delete temporaries and fail with a message telling `qa-pr` to use screenshots/GIFs. Validate final codec, pixel format, duration, dimensions, and size with `ffprobe` before atomic rename.

- [ ] **Step 4: Verify and commit**

Run: `bash qa-pr/tests/test-normalize-video.sh`

Expected: PASS.

Run: `shellcheck qa-pr/scripts/normalize-video.sh qa-pr/tests/test-normalize-video.sh` when `shellcheck` is installed; otherwise record that it was unavailable and rely on `bash -n`.

```bash
git add qa-pr/scripts/normalize-video.sh qa-pr/tests/test-normalize-video.sh
git commit -m "feat: normalize qa browser recordings"
```

### Task 3: Rewrite the `qa-pr` workflow around hosted video evidence

**Files:**
- Modify: `qa-pr/SKILL.md`

**Interfaces:**
- Consumes: `agent-browser record start/stop`, Tasks 1–2 helpers, and `snapdoc publish ... --json`.
- Produces: one sticky forge comment with video/poster/watch evidence or explicit screenshot/GIF fallback.

- [ ] **Step 1: Write a failing static contract check**

Before editing, run the following and expect at least one missing pattern:

```bash
for needle in \
  'agent-browser record start' \
  'normalize-video.sh' \
  'snapdoc publish' \
  'render-video-evidence.py' \
  'GitLab' \
  'new video artifact for every QA run' \
  'degraded evidence'; do
  rg -F "$needle" qa-pr/SKILL.md >/dev/null || echo "MISSING: $needle"
done
```

- [ ] **Step 2: Replace the media-capture section**

Specify this exact order:

1. Complete `qa-ticket` and all fixes/retries without recording.
2. Re-establish the known-good page/state and choose only meaningful frontend acceptance cases.
3. Start `agent-browser record start <scratch>/qa.webm`; replay; stop.
4. Invoke `<skill-dir>/scripts/normalize-video.sh` to create MP4/poster.
5. Inspect duration/size and confirm no sensitive content.
6. Show the video path, poster, exact proposed comment, and expiry at the existing first-post checkpoint.
7. Run `snapdoc publish <mp4> --title "<repo> PR #<n> QA @ <sha>" --ttl 3d --poster <jpg> --json`.
8. Save JSON only in scratch space and invoke the forge renderer.
9. Add the fragment to the evidence table/comment and upsert the sticky marker.

State explicitly that each run creates a new artifact and that video generation happens only for frontend flows; static UI states remain screenshots and backend cases remain curl request/response evidence.

- [ ] **Step 3: Add forge detection and sticky-update instructions**

Detection precedence is explicit PR/MR URL, then `git remote get-url origin`. Document:

- GitHub: `gh pr view/comment`; find marker through `gh api`, PATCH existing issue comment or create once.
- GitLab: `glab mr view`; list project MR notes through `glab api`, PUT the marked note or POST once.
- Bitbucket: create with `bt pr comment <id> -b "<body>"`. For sticky lookup/update, require `BITBUCKET_TOKEN` and call `GET /2.0/repositories/{workspace}/{repo}/pullrequests/{id}/comments?pagelen=100`, then `PUT /2.0/repositories/{workspace}/{repo}/pullrequests/{id}/comments/{comment_id}` with `{"content":{"raw":"<body>"}}`. If a rerun cannot authenticate to list/update comments, stop and ask rather than posting a duplicate.

Keep the bot header and `<!-- qa-pr-evidence -->`; add `<!-- qa-pr-video artifact="..." version="1" sha="..." -->`. Preserve previous SHA/verdict lines in the collapsed history, not expired media embeds.

- [ ] **Step 4: Add failure, privacy, and passcode rules**

For each failure boundary—record, normalize, poster, Snapdoc, renderer—state the exact fallback: retain screenshots/GIFs, add `⚠️ Video evidence unavailable: <stage> failed`, and continue assembling the QA verdict. Passcode mode must call the renderer with protected JSON and must never manually paste the raw file URL.

Repeat that real credentials, production/staging data, password entry, console tokens, unrelated tabs, and desktop content must not be recorded.

- [ ] **Step 5: Verify the skill contract and helper tests**

Run the static contract loop from Step 1 again.

Expected: no `MISSING` lines.

Run:

```bash
python3 qa-pr/tests/test_render_video_evidence.py -v
bash qa-pr/tests/test-normalize-video.sh
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add qa-pr/SKILL.md
git commit -m "feat: post hosted video evidence from qa-pr"
```

### Task 4: Run a local dry run and prepare controlled forge smoke tests

**Files:**
- Repair target when a check fails: `qa-pr/SKILL.md`
- Repair target when normalization fails: `qa-pr/scripts/normalize-video.sh`, `qa-pr/tests/test-normalize-video.sh`
- Repair target when markup fails: `qa-pr/scripts/render-video-evidence.py`, `qa-pr/tests/test_render_video_evidence.py`

**Interfaces:**
- Consumes: completed Snapdoc local server/CLI and Tasks 1–3.
- Produces: verified local evidence artifact and three unposted forge comment bodies.

- [ ] **Step 1: Exercise capture against a disposable localhost page**

Use a non-sensitive local page, establish browser state, record a two-step flow with `agent-browser`, normalize it, and inspect the MP4/poster locally. Do not open a real PR/MR or post comments.

- [ ] **Step 2: Publish only to a local Snapdoc Worker**

Use the local API/token and the locally built CLI. Confirm JSON includes HTTPS-shaped watch/file/poster fields if the local test harness rewrites hosts, or substitute a recorded fixture JSON for renderer tests. Verify the artifact default expiry is three days and raw range requests work.

- [ ] **Step 3: Render all three unposted comment fragments**

Run the renderer for GitHub, GitLab, and Bitbucket. Inspect that:

- GitHub contains `<video>` and a watch fallback.
- GitLab contains `![QA recording](...mp4)` and a watch fallback.
- Bitbucket contains a poster linked to the watch page and a watch fallback.
- Protected JSON produces no inline file/poster URL.

- [ ] **Step 4: Run final repository checks**

```bash
python3 qa-pr/tests/test_render_video_evidence.py -v
bash qa-pr/tests/test-normalize-video.sh
git diff upstream/main...HEAD --stat
git status --short
```

Expected: tests PASS; no recordings, generated MP4s/posters, tokens, or scratch JSON are tracked.

- [ ] **Step 5: Commit verification fixes if and only if needed**

```bash
git add qa-pr/SKILL.md qa-pr/scripts qa-pr/tests qa-pr/references
git commit -m "fix: harden qa video evidence workflow"
```

If no fixes were needed, do not create an empty commit. Stop and request explicit approval before the first real GitHub, GitLab, or Bitbucket comment or any remote Snapdoc upload.
