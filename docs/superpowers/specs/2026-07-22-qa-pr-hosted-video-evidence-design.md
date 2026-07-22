# QA PR Hosted Video Evidence Design

**Date:** 2026-07-22
**Status:** Approved for planning

## Goal

Upgrade `qa-pr` so a reviewer can observe the behavior tested at an exact PR
commit without reproducing the local environment. A run produces one navigable
evidence bundle: a chaptered MP4, a Snapdoc Markdown report, and the existing
sticky PR comment.

The bundle must make each claim traceable to an acceptance case, bind the
evidence to the commit and environment that produced it, expire predictably,
and avoid exposing credentials or private test data.

## Scope

The upgrade adds:

- frontend recording with `agent-browser`;
- deterministic WebM-to-MP4 assembly and one chapter per recorded acceptance
  case;
- Snapdoc video and Markdown-report publishing;
- a Mermaid requirement-to-case-to-result map in the report;
- visibility-aware privacy and expiry controls;
- an exact commit/environment manifest;
- stable artifact reuse on reruns; and
- posting gates that prevent evidence from being attributed to the wrong PR
  commit.

Backend-only PRs and runs with no meaningful visual cases publish the report
without an empty or decorative video. This upgrade does not change how
`qa-ticket` derives or executes acceptance tests.

## Approaches Considered

### One video per case

This makes each case independently playable and avoids concatenation, but it
creates many hosted artifacts and makes the PR comment noisy. Artifact lifecycle
and privacy changes also become repetitive.

### Video only

This minimizes artifact count, but backend evidence, timestamps, the manifest,
and requirement traceability have no readable home. The PR comment becomes the
entire report and loses scanability.

### Evidence bundle (selected)

One chaptered MP4 contains the frontend demonstrations. One Markdown report
indexes video chapters, screenshots, backend request/response evidence, the
Mermaid traceability map, and the manifest. The sticky PR comment remains a
compact entry point. This yields one review surface without flattening unlike
evidence into the video.

## Components

### `qa-pr/SKILL.md`

The main skill remains the ordered control plane. It owns PR checkout, privacy
selection, evidence gates, orchestration of `qa-ticket`, capture timing,
Snapdoc publication, and sticky-comment upsert. It points to the detailed
evidence contract only when the run has evidence to assemble.

The existing `qa-ticket` relationship remains the single source of truth for
test-plan generation and execution. `qa-pr` consumes stable case IDs and results;
it does not restate the test-planning rules.

### Video assembly helper

Add a reusable helper under `qa-pr/scripts/` with a machine-readable input and
output contract. The input is an ordered JSON list of recorded cases:

```json
[
  {"id": "T1", "title": "Create an invoice", "file": "/tmp/qa-pr/T1.webm"},
  {"id": "T4", "title": "Reject an invalid total", "file": "/tmp/qa-pr/T4.webm"}
]
```

The helper uses `ffmpeg` and `ffprobe` to normalize and concatenate the clips,
mux MP4 chapter metadata, create a poster, and calculate the final SHA-256. It
outputs:

- `evidence.mp4`, encoded as H.264 with optional AAC audio;
- `poster.jpg`;
- `chapters.json`, containing ordered `start_ms`, `end_ms`, and duration values;
  and
- a non-zero exit with an actionable message when a required tool, input, codec,
  duration, or size constraint fails.

The helper enforces Snapdoc's limits before upload: at most 10 minutes and
100,000,000 bytes. Case IDs are unique, every clip is non-empty, and chapter
ranges are contiguous and ordered.

### Evidence-format reference

Add a disclosed reference under `qa-pr/references/` containing the report and
sticky-comment contracts. This keeps conditional video/report detail out of the
main workflow while preserving one authoritative format.

## Run Flow

### 1. Resolve the immutable QA target

Fetch the PR number, URL, repository visibility, head branch, base branch, head
OID, and base OID. Check out the PR in an isolated worktree. Capture the initial
HEAD and worktree state.

Run `qa-ticket` to produce stable acceptance-case IDs and results. If it creates
fix commits, finish QA against the new clean HEAD, then require that HEAD to be
present as the PR's current remote `headRefOid` before any evidence is posted.
The run can be assembled locally while that condition is false, but it cannot be
represented on the PR as evidence for an unpushed commit.

### 2. Capture cases

Frontend flows are explored and made deterministic before recording. Each
meaningful frontend case gets its own `agent-browser record start`/`stop` clip
using a consistent viewport and session state. Recording starts from the case's
known initial state and ends only after the observable assertion is visible.

Backend cases retain their actual request and response as text. A screenshot is
included only when the backend action has a relevant UI effect. A backend-only
run skips video assembly.

Capture uses dev/test authentication and synthetic or approved fixture data.
Before publication, inspect every captured frame class and the report inputs for
credentials, tokens, personal data, unrelated browser chrome, and incorrect
tenant/customer context. The capture step is complete only when every published
case has a result and sanitized evidence.

### 3. Assemble the bundle

Feed passing and failing recorded cases to the video helper in test-plan order.
The resulting chapter titles use `<case ID> — <short case title>`. Generate
timestamp links against Snapdoc's version-pinned raw `version_file_url` using
media fragments such as `#t=12.400`.

Snapdoc's native watch page does not currently expose a chapter selector. The
report's timestamp table is therefore the browser-visible chapter interface;
the MP4 chapter metadata preserves the same structure for players that support
it.

Generate the Markdown report with:

1. verdict and tested commit;
2. Mermaid requirement → acceptance case → result traceability;
3. a per-case table with category, result, timestamp/screenshot/request evidence,
   and concise notes;
4. bugs found and fix SHAs;
5. artifact expiry and privacy posture; and
6. the commit/environment manifest.

Mermaid blocks include `accTitle` and `accDescr`. The Markdown source remains the
canonical report input; Snapdoc renders and hosts it.

### 4. Checkpoint privacy and outward publication

Assemble evidence locally before the first outward action. The existing first-run
checkpoint shows the verdict, media list, manifest summary, repository visibility,
chosen privacy, TTL, and a PR comment preview with clearly marked hosted-URL
slots (the exact URLs do not exist until publication succeeds).

Privacy policy:

- Public repository: default to an unlisted, unprotected bundle with a 3-day TTL.
- Private repository: require an explicit unlisted-versus-passcode choice at the
  checkpoint, recommending unlisted with a 3-day TTL.
- Passcodes are supplied to Snapdoc only and shared with reviewers out-of-band.
  The PR comment links the protected watch/report pages and does not embed media
  or contain the passcode.
- A user may override video/report TTL together. Video bounds control the shared
  value: 1 hour through 7 days.

The Snapdoc preflight verifies authentication and video support. Concretely,
`snapdoc whoami` must succeed and `snapdoc publish --help` must expose
`--poster`. A stale CLI stops with an upgrade instruction before recording work
is wasted.

### 5. Publish and upsert

Publish the MP4 first with `snapdoc publish evidence.mp4 --json`, the selected
TTL/privacy, title containing the PR and short SHA, and the generated poster.
Then generate final timestamp links from the returned `version_file_url`, publish
the Markdown report, and post or patch the sticky PR comment.

The comment stores machine-readable HTML markers for the video and report
artifact IDs. A rerun reads those markers and uses `snapdoc publish --update` so
the stable URLs remain stable. The latest section links current stable URLs;
previous-run entries link version-pinned URLs and state the tested SHA.

Artifact reuse is allowed only when the privacy posture is unchanged. A policy
change creates a new artifact pair after a fresh checkpoint; the prior pair is
left intact unless the user asks to expire it.

Immediately before comment upsert, refetch the PR. Posting requires:

- clean worktree;
- local HEAD equals the manifest head SHA;
- remote PR `headRefOid` equals that SHA; and
- video/report hashes and case results match the assembled comment.

### 6. Report locally

Return the verdict, tested SHA, case results, watch/report/comment URLs, expiry,
privacy posture, artifact versions, and any bugs fixed. If no video was warranted,
say so directly and return the report/comment URLs.

## Evidence Manifest

The report records:

| Field | Meaning |
| --- | --- |
| PR | repository, PR number, and PR URL |
| Commit | tested head SHA and base SHA |
| Worktree | clean state at capture and publication gates |
| Plan | SHA-256 of the normalized acceptance-case plan |
| Capture | UTC timestamp, browser/version, viewport, and case count |
| Application | sanitized localhost origins, auth mode label, and fixture/data-set label |
| Tools | `qa-pr`, `agent-browser`, `ffmpeg`, and Snapdoc versions |
| Video | SHA-256, duration, dimensions, codec, and ordered chapters |
| Publication | privacy posture, expiry, Snapdoc artifact IDs and versions |

Secrets, cookies, raw environment-variable values, passwords, and passcodes are
outside the manifest contract.

## Failure Handling

- A missing or stale Snapdoc CLI, failed authentication, or unreachable Snapdoc
  API fails preflight before capture.
- A failed case remains visible as failed evidence; it is not omitted from the
  report or chapter list when a recording exists.
- A failed video conversion names the case/clip and leaves source clips available
  for retry.
- If the video publishes but the report fails, retain the video URL locally,
  retry the report, and leave the PR unchanged until the bundle is complete.
- If PR head changes during QA, mark the local bundle stale and rerun against the
  new head rather than posting mismatched evidence.
- If a poster upload alone fails, use Snapdoc's poster-only retry without creating
  a new video version.
- If the bundle exceeds Snapdoc duration or size limits, split only at acceptance-
  case boundaries into the smallest number of videos and index all parts from the
  single report. This is an exceptional branch, not the default format.

## Verification Strategy

### Skill RED/GREEN scenarios

Before editing the skill, run fresh-agent baseline scenarios against the current
`qa-pr` and capture the observed omissions. Re-run the same scenarios with the
edited skill:

1. first run on a public frontend PR;
2. first run on a private PR where unlisted is selected;
3. protected evidence, verifying link-only output and out-of-band passcode;
4. a rerun that must reuse stable artifact IDs and pin prior versions;
5. local fixes whose SHA is not yet the remote PR head;
6. backend-only QA where video should be skipped; and
7. stale Snapdoc CLI preflight.

Success means the agent follows the same gates and produces every required
evidence field under time pressure without duplicating `qa-ticket` behavior.

### Helper tests

Test malformed input, duplicate/missing case IDs, missing clips, tool failures,
ordered chapter ranges, metadata escaping, silent recordings, poster generation,
duration/size rejection, and stable JSON output. An integration fixture verifies
the final file with `ffprobe`: MP4 container, H.264 video, optional AAC audio,
chapter count and titles, duration, and dimensions.

### Static checks

Validate skill frontmatter, referenced paths, script `--help`, report/comment
markers, and shell examples. Run the repository's existing skill checks if
present. Confirm Snapdoc `0.0.10` or newer exposes the required video publish
contract.

## Rollout

The implementation changes only `qa-pr` and its local helper/reference/test
files. It does not modify Snapdoc or `qa-ticket`. The first real PR run remains
behind the existing checkpoint, providing a safe production smoke test. The old
screenshot/GIF path remains a fallback when video prerequisites fail and the user
explicitly chooses to proceed without hosted video.
