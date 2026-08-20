---
name: qa-pr
description: Use when the user wants to QA a GitHub or Bitbucket PR and leave observable acceptance-test evidence on the PR for reviewers.
---

# QA PR: publish proof bound to a PR commit

Proof binds observable behavior to the exact commit a reviewer can inspect.
`qa-pr` invokes `qa-ticket` for test selection, execution, fixes, and retries; it
adds PR checkout, deterministic evidence capture, hosted video/report lifecycle,
and exactly one upserted PR comment. Do not duplicate `qa-ticket`'s planning or
testing logic.

Every frontend run publishes **both** forms of evidence, because they prove
different things and neither substitutes for the other:

- The **video** shows a reviewer that the behavior really happens, in order, in a
  real browser.
- The **report** states what was asserted, in machine-checkable terms: the exact
  post-action text, attributes, or payload each case turned on, quoted verbatim.

A video alone leaves a reviewer squinting at pixels to guess the assertion, and
is especially weak for negative claims — "the slide did *not* move" looks like
nothing happening. A report alone leaves them trusting a transcription. Publish
both, and make each case's row link to both.

All testing is localhost-only. Never test staging or production. Never publish
evidence unless the user asked to place it on that PR.

Before assembling or updating evidence, read
`references/evidence-format.md`. It owns the report, manifest, chapter links,
hidden artifact markers, and video-present/report-only sticky-comment forms.

## 1. Resolve the immutable target

Resolve the forge, PR URL/number, repository, repository visibility, head/base
refs, full head/base OIDs, and title. GitHub requires `headRefOid`:

```bash
gh pr view <pr> --json number,url,title,headRefName,headRefOid,baseRefName,baseRefOid
gh repo view --json nameWithOwner,visibility
```

Use the Bitbucket equivalent through `bt`. If repository visibility cannot be
determined, handle it as private/unknown.

Create or reuse an isolated worktree at the resolved PR head. Record:

```bash
git rev-parse HEAD
git status --porcelain
```

The worktree must be clean before capture. Derive ticket context from the branch
or PR, but let `qa-ticket` fetch and interpret it.

## 2. Preflight before testing

Complete this gate in order:

1. Require `agent-browser`, `ffmpeg`, `ffprobe`, and `snapdoc` on `PATH`.
2. Run `snapdoc whoami`; authentication and the configured API must work.
3. Run `snapdoc publish --help` and require both `--poster` and `--watch-only`.
   This proves the installed Snapdoc supports native video evidence and can
   withhold the raw media URL.
4. Discover the localhost frontend/backend origins, route, auth mode, and fixture
   or data setup. Record sanitized labels for the manifest.
5. Verify the local app and auth/session endpoint before opening the feature.
6. Record browser, viewport, tool versions, UTC time, clean state, and local HEAD.
7. **Prove capture works before running the test pass.** Record one throwaway
   clip of any page — start, interact once, stop — and require a playable file
   whose `ffprobe` duration is greater than zero. Discard it.

Step 7 is not ceremony. Capture can fail long after `record start` reports
success, and discovering that only at the end means the whole pass was run
un-recorded and has to be replayed. Prove it on a throwaway clip, not on evidence.

If Snapdoc authentication/API is unavailable, stop before capture: neither the
video nor the hosted report can be completed. If Snapdoc is older than `0.0.10`
or lacks `--poster`, state the installed version and stop with an instruction to
upgrade before capturing anything.

If the capture smoke test fails, switch recorders before considering any degraded
path — see the fallback recorder in section 3. Report-only is correct for a
backend-only run, and is otherwise a last resort that requires telling the user
what broke and getting their choice. It must be labeled in the report; never
imply a bundle contains video when it does not.

Get past authentication with the app's test/dev bypass or browser state supplied
by the user. Never request a password or drive a real login. Forward remote dev
ports so the browser still reaches `localhost`; a LAN, staging, or production URL
is not an acceptable substitute.

## 3. Run qa-ticket, then record deterministic clips

Invoke `qa-ticket` in the PR worktree. Consume its stable case IDs, categories,
expected results, actual results, verdict, and fix SHAs. Verify routes before
calling a result a product failure.

Keep passing and failing acceptance cases in plan order. A failed case remains
visible in the report and receives a chapter whenever a meaningful recording
exists; never omit failure evidence to improve the verdict.

Finish exploration, fixture setup, diagnosis, fixes, and route discovery before
recording. A QA recording is a clean replay, not a debugging session.

For each meaningful frontend case:

1. Reset to a known initial state.
2. Start one recording named for its stable case ID.
3. Replay only the known deterministic actions.
4. Stop when the observable assertion is visibly settled.
5. Capture the case's **verbatim assertion** — the exact post-action text,
   attribute, or state object the case turned on — for the report's observation
   section. Quote what the page actually returned; never paraphrase it.
6. Capture a key-state screenshot when it helps scanning or becomes the poster.

```bash
agent-browser record start <scratch>/<case-id>.webm
# deterministic actions and visible assertion
agent-browser record stop
```

Step 5 is what makes the report worth reading on its own. Prefer an assertion a
reviewer can check against the code: the rendered indicator text, the element's
`aria-*`/`inert` attributes, the number of matching nodes, an `innerHTML` showing
that hostile content stayed escaped, the request that did or did not fire. For a
negative claim, capture the value on both sides of the action so "unchanged" is
visible rather than asserted.

Do not record setup, waiting, unrelated navigation, or duplicate cases. Inspect
the clips, screenshots/frames, visible inputs, and browser chrome before hosting.
Reject and recapture evidence containing secrets, credentials, cookies, personal
or private tenant data, incorrect tenant context, or unrelated windows/tabs.

### Fallback recorder

When the capture smoke test fails, do not spend the run debugging the recorder.
Check whether the repository already depends on Playwright, and if it does, record
with it instead — one browser context per acceptance case, which yields one clean
clip per case and finalizes on close:

```js
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  recordVideo: { dir: tmp, size: { width: 1280, height: 720 } },
});
// deterministic actions and visible assertion
await context.close(); // writes the .webm; rename it to <case-id>.webm
```

Import Playwright from the repository's own install rather than adding a
dependency, and keep the script in scratch so the worktree stays clean:
`createRequire("<worktree>/frontend/package.json")`. A fresh context per case also
gives each case isolated storage, so a prior case's saved answers cannot leak in.
Scope every locator to the visible subtree when the UI keeps offscreen copies in
the DOM, or strict mode matches the hidden ones.

Whichever recorder produced the clips, name it in the report's manifest, and add a
short capture note when it was not the default one. A reviewer who later cannot
reproduce a clip needs to know what made it.

Backend evidence is the exact sanitized request and response text. A screenshot
or decorative video never replaces request/response evidence. When every case is
backend-only, skip video creation and publish the report-only form.

## 4. Build the chaptered video

Write an ordered `cases.json` whose entries are `{id, title, file}` and whose
order matches the report. Run:

```bash
python3 <qa-pr-skill>/scripts/build-video-evidence.py \
  --cases <scratch>/cases.json \
  --output-dir <scratch>/video
```

The command must produce `evidence.mp4`, `poster.jpg`, and `chapters.json`.
Verify the manifest reports H.264, yuv420p, silence, dimensions at most 1280x720,
duration at most 600 seconds, size at most 100,000,000 bytes, the MP4 SHA-256,
and one contiguous ordered chapter per case.

If the combined bundle exceeds a Snapdoc limit, partition only at acceptance-case
boundaries into the smallest number of contiguous ordered parts. Build
`cases-part-N.json` once per part and index all parts from the single report. Never
split a case to make a limit fit. One video remains the normal path.

## 5. Build the report and bind it to the commit

Normalize the final test plan before hashing it: serialize the ordered case IDs,
categories, descriptions, expected results, and actual results as UTF-8 JSON with
sorted object keys, compact separators, LF endings, and one terminal newline.
Record its SHA-256.

Render the report from `references/evidence-format.md` with:

- a Mermaid requirement → acceptance case → observed result graph using
  accessible `accTitle` and `accDescr`;
- a concise acceptance-case table whose every frontend row links **both** its
  video chapter and its observation section;
- timestamp links of the form `version_url?t=<seconds.milliseconds>` for
  every video chapter;
- one observation section per case holding the verbatim assertion from step 5,
  in a fenced block, plus a fixtures table when seeded data shaped the run;
- sanitized backend request/response sections;
- fix commits and retests; and
- the complete commit/environment/publication manifest from the reference.

A case that has a chapter but no observation is unfinished: the reviewer can see
it happen but cannot check what it was supposed to prove. A case whose behavior
has no motion to record — a pure attribute or payload check — carries its
observation alone, and the table says so rather than linking a chapter that does
not exist.

The report table is the browser-visible chapter navigator. Snapdoc's watch page
does not provide one, but it does honor `?t=`, so every chapter link opens the
watch page seeked to that moment.

Never timestamp the raw media URL. A `#t=` on `version_file_url` bypasses the
watch page, so on protected or watch-only evidence it lands the reviewer on a
bare 401/403 with nothing to act on. `version_url?t=` resolves to the unlock
prompt when locked and survives the unlock redirect.

After any fix, require a committed, clean local HEAD. Immediately before the
first outward action, refetch the live PR and require:

```text
clean local worktree
local HEAD == manifest head SHA == current PR headRefOid
```

For Bitbucket, compare the equivalent current source commit. If any value differs,
mark the local bundle stale and stop without uploading or commenting. Ask the user
to push/update the PR, then revalidate the remote head and evidence. Never post a
claim for a local-only commit, even when labeled local-only.

## 6. Choose privacy and checkpoint

The first outward-action checkpoint happens before any Snapdoc upload or PR
comment. Show the user:

- verdict and exact full SHA;
- per-case results;
- video parts, screenshots, and report inventory;
- manifest summary;
- repository visibility;
- proposed privacy and expiry;
- the complete proposed sticky comment with hosted-URL placeholders.

Defaults and allowed choices:

- Every repository, public or private: passcode-protect both artifacts, expiring
  in 3 days. The passcode is generated fresh at publish time and published in the
  sticky comment's 🔒 line, so evidence access is gated by repository read
  access — a leaked watch or report URL alone reveals nothing.
- Unlisted is an opt-out the user must ask for. Honor it when they do, and
  explain that anyone holding the URL can then view the evidence.
- Snapdoc accepts TTLs from 1 hour through 7 days. Never silently make evidence
  permanent or extend its expiry.

The existing marked comment is authorization to rerun with the same destination,
privacy, and non-expanded expiry. A first publication or any destination, privacy,
or expiry expansion requires a fresh checkpoint.

Generate the passcode at publish time with `openssl rand -hex 8` and pass it
explicitly via `--passcode` to both Snapdoc create invocations (video and
report). Never let `SNAPDOC_PASSCODE` or the config file supply it implicitly —
an inherited value may not match what the comment publishes. The sticky
comment's 🔒 line is the passcode's single published location: keep it out of
the report, the manifest, and the hidden markers, so one comment PATCH always
shows the current code. On a rerun that keeps protection, reuse the passcode
parsed from the existing 🔒 line; updates retain the artifact's protection and
do not receive `--passcode`.

Snapdoc also resolves `--passcode` from `SNAPDOC_PASSCODE` and the config file
when the flag is absent, which is exactly why the flag must carry the generated
value. Never infer protection from the command line: read `has_passcode` in
each create response and require `true` on both artifacts. If either comes back
`false`, the evidence is unprotected — do not comment on the PR. Apply `snapdoc
protect <id> --passcode <code>` to the affected ID, confirm `has_passcode` is
now `true`, and only then continue.

Both artifacts carry the same protection. Protecting only the video leaves the
report — which holds the case table, observations, and manifest — readable by
anyone with its link.

Changing privacy on a rerun does not require new artifacts. `snapdoc protect <id>
--passcode <code>` adds or rotates protection, and `--remove-passcode` drops it,
all while keeping the artifact ID — so links already posted on the PR keep
working. Rotating also revokes every open unlock session and viewer link. Apply
`protect` to both the video and report IDs with a freshly generated
`openssl rand -hex 8` value, then PATCH the sticky comment so its 🔒 line shows
the new code — the old one stops working the moment `protect` succeeds.

## 7. Publish or update stable Snapdoc artifacts

Read the existing `<!-- qa-pr-evidence -->` comment before publishing. Parse its
video/report artifact IDs, ordered `part` attributes, privacy, expiry, the
🔒 line's current passcode, current stable links, and Previous runs
version-pinned links.

Update the same artifact IDs so current URLs stay stable. This holds even when
privacy changes: apply `snapdoc protect` to the existing IDs rather than minting
replacements.

```bash
snapdoc publish <evidence.mp4> --json --ttl <ttl> \
  --title "<owner/repo> PR #<number> QA @ <short-sha>" \
  --poster <poster.jpg> --update <video-id>
snapdoc publish <report.md> --markdown --json --ttl <ttl> \
  --title "<owner/repo> PR #<number> QA report @ <short-sha>" \
  --update <report-id>
```

For multipart video, match IDs by ordered part number. Reuse matching parts and
create only newly required parts. Do not silently expire a removed or superseded
artifact; show it in the checkpoint and follow the user's retention choice.

For a first publication or a missing ID, create artifacts:

```bash
snapdoc publish <evidence.mp4> --json --ttl <ttl> --watch-only --passcode <code> \
  --title "<owner/repo> PR #<number> QA @ <short-sha>" --poster <poster.jpg>
snapdoc publish <report.md> --markdown --json --ttl <ttl> --passcode <code> \
  --title "<owner/repo> PR #<number> QA report @ <short-sha>"
```

Pass the generated `--passcode` on both creates unless the user opted out to
unlisted at the checkpoint. Confirm `has_passcode` in each response as described
in section 6.

Always create video evidence `--watch-only`. The evidence format links the watch
page and never embeds the MP4 inline, so nothing is lost, and the recording stops
being hotlinkable by anyone who obtains the media URL. A watch-only artifact
reports `file_url` and `version_file_url` as `null`; use `version_url` for every
chapter link and manifest field.

Publish video first and save each JSON response in scratch. Use its artifact ID,
version, and `version_url` to finish the report's timestamp and manifest fields.
Then publish the report and save its JSON response.

The report must name its own artifact ID and version. On the first run, bootstrap
it once: create the report, take the returned ID, render that ID and expected
version 2 into the complete report, then update the same ID and verify the response
is version 2. On reruns, read the current report version with `snapdoc get <id>
--json`, render the expected next version, publish one update, and verify the
returned version. If the version is not the rendered value, correct the manifest
by updating the same report ID again; never mint a replacement merely to repair
self-metadata.

If video succeeds but report publication fails, keep the video response, leave the
PR unchanged, and retry the report; do not create another video. If only poster
upload fails, use Snapdoc's poster-only retry rather than uploading a new version:

```bash
snapdoc publish --json --update <video-id> --poster <poster.jpg>
```

The PR contains only watch/report links. Never embed or link a raw media URL —
watch-only evidence has none to link. The current passcode appears exactly once
on the forge: in the sticky comment's 🔒 line.

## 8. Final gate and sticky-comment upsert

Load the correct form from `references/evidence-format.md`. Preserve prior-run
report/video URLs as version-pinned links. Keep the new stable watch/report URLs
prominent and store the current artifact IDs in hidden markers.

Refetch the PR source SHA one final time and recheck the clean three-way equality.
If it moved after upload, do not post stale evidence; retain the returned Snapdoc
JSON, rerun/revalidate, and update the same artifacts only when safe.

Before comment upsert, also verify the published video/report hashes and case results
match the manifest, report, and proposed comment. A mismatch is stale evidence:
stop and rebuild or rerender it instead of posting inconsistent proof.

Confirm the published protection matches what the checkpoint approved: re-read
`has_passcode` on both artifacts and require it to agree with the `privacy` value
going into the manifest and hidden state. Posting a comment that calls evidence
protected when it is not is a false claim about who can read it.

Find the one comment containing `<!-- qa-pr-evidence -->`:

- If absent, create it after the approved checkpoint.
- If present, PATCH that exact comment.
- If the forge/connector cannot update it, stop. Never create a duplicate.

For GitHub, use `gh` to create or PATCH the marked comment. For Bitbucket,
preserve the existing `bt pr comment`/comment-update behavior; if update support
is unavailable, stop instead of adding a second comment.

## 9. Completion report

Return all of the following:

- verdict and exact tested SHA;
- stable case IDs and results;
- stable video watch URL(s), report URL, and sticky-comment URL;
- privacy, expiry, artifact IDs, and artifact versions;
- MP4 and test-plan SHA-256 values;
- bugs fixed and their commit SHAs;
- which recorder produced the clips, when it was not the default one; and
- whether the run was video+report, multipart, or backend-only report.

Do not claim completion unless preflight passed, every capture was inspected,
every case carries its verbatim observation, the publication manifest is complete,
the clean three-way SHA gate passed twice, and exactly one marked PR comment
exists.

Findings outside the tested change are worth surfacing, but not silently: report
them to the user rather than folding them into the PR's verdict, say plainly
whether the PR caused them, and let the user decide whether they become a ticket.
