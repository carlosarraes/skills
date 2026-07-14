---
name: video-extract
description: >
  Use when the user wants the transcript(s) of one or more YouTube videos —
  "extract this video", "get the transcript", "video-extract <url>", "pull these
  talks", "transcribe this", "mine this talk", or pastes YouTube links to read/
  summarize. Handles a batch of videos, captions-first (fast, free), with an
  audio-transcription fallback for videos that have none. Produces clean plain-
  text transcripts ready to read or mine for ideas.
---

# Video Extract: YouTube → clean transcript

Pulls readable transcripts from one or more YouTube videos so you can read, skim,
or mine a talk without watching it. **Captions-first**: nearly every video has
auto-captions, and grabbing them is instant and free — no download, no
transcription API. (This is what the `pi` `video-extract` extension does under
the hood: `yt-dlp` + `ffmpeg` + Gemini. It is not pi-specific — the tools are
standard, and captions alone usually suffice.)

Requires `yt-dlp` and `python3` on PATH (plus `ffmpeg` + a Gemini/whisper key
only for the audio fallback).

## Workflow

### Step 1: Collect the videos

Accept one or more URLs or bare IDs (`https://www.youtube.com/watch?v=ID`,
`youtu.be/ID`, or `ID`). Process each independently; if one fails, report it and
keep going. Pick an output dir — the session scratchpad by default, or a path the
user gives.

### Step 2: Per video — metadata + caption availability

```bash
yt-dlp --skip-download \
  --print "%(id)s | %(title)s | %(duration>%H:%M:%S)s | %(channel)s | %(upload_date)s" \
  "<url>"
# what captions exist (read-only):
yt-dlp --list-subs --skip-download "<url>" 2>&1 | sed -n '/subtitles/,/automatic/p' | head
```

**Language choice:** prefer a **manual** subtitle in the video's original
language; else the **auto-caption in the original language**; else English
auto-caption (`--sub-lang en`). YouTube auto-translates auto-captions into every
language, so don't grab a translated track when the original exists — it's a
worse, machine-translated copy.

### Step 3: Fetch captions and clean them

```bash
yt-dlp --skip-download --write-auto-sub --sub-lang <lang> --sub-format vtt \
  -o "<outdir>/%(id)s.%(ext)s" "<url>"
python3 <skill-dir>/references/vtt-to-text.py "<outdir>/<id>.<lang>.vtt" \
  > "<outdir>/<id>.txt"
```

Use `--write-sub` (not `--write-auto-sub`) when a manual track was chosen. The
cleaner strips cue timestamps, inline word-timing tags, and the rolling-caption
repeats that otherwise triple every line. Report the resulting word count.

### Step 4: Fallback — transcribe audio (only when there are NO captions)

Rare, but some videos have captions disabled. Then download audio and transcribe:

```bash
yt-dlp -x --audio-format mp3 -o "<outdir>/%(id)s.%(ext)s" "<url>"
```

Transcribe the mp3 with whatever is available — a local `whisper`, or the Gemini
API (`GEMINI_API_KEY`/`GOOGLE_API_KEY`; upload the file and ask for a transcript).
State clearly if no transcription backend is configured rather than silently
producing nothing. This path costs time/tokens; skip it whenever captions exist.

### Step 5: Report

Per video: `id`, title, duration, chosen language, word count, and the transcript
file path. If the user's intent was to mine/summarize (a talk, a lecture), offer
to read the transcript(s) and pull out the key ideas — don't dump the raw text
into chat.

## Constraints

- **Captions-first, always.** Only touch the audio-transcription fallback when a
  video genuinely has no captions. It's slower and needs a key.
- **Original language over auto-translation.** A machine-translated caption track
  is a lossy copy of the original auto-caption — prefer the source language.
- **Always clean the VTT.** Never hand back raw VTT; run `vtt-to-text.py` so the
  output is prose, not timestamped rolling-caption noise.
- **Batch-resilient.** One bad/unavailable video doesn't abort the rest.
- **Public videos only.** This fetches public content; don't attempt
  age-gated/private/members-only videos that need auth.
- **Write transcripts to a working dir**, not into a code repo.
