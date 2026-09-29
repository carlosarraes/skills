#!/usr/bin/env node
// Measure what a repository's GitHub Actions runs cost and how long they take,
// per workflow and per job.
//
// Usage: node measure.mjs OWNER/REPO [--days 14] [--out jobs.json] [--cache FILE]
// Needs: Node 18+ and the GitHub CLI (`gh auth login`) with read access to Actions.
//
// Billing follows GitHub's rules for standard hosted runners: each job rounds up
// to a whole minute, Windows counts twice, macOS ten times, and skipped jobs are
// free. Jobs on any other runner group (self-hosted or larger runners) are
// listed apart, because they are either free or billed at their own rate.
//
// Rate limits: the REST API allows 5,000 requests an hour and a busy repo needs
// one request per run attempt. The script checks the budget as it goes, sleeps
// until the window resets instead of failing, retries secondary limits with
// backoff, and caches finished runs' jobs so an interrupted run resumes.
import { execFile } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { promisify } from "node:util";

const exec = promisify(execFile);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : fallback;
};
const repo = args.find((a, i) => a.includes("/") && !args[i - 1]?.startsWith("--"));
if (!repo) {
  console.error("Usage: node measure.mjs OWNER/REPO [--days 14] [--out jobs.json] [--cache FILE]");
  process.exit(2);
}
const days = Number(option("days", 14));
const outFile = option("out", "");
const cacheFile = option("cache", `.measure-cache-${repo.replace("/", "-")}.json`);

// `rate_limit` itself does not count against the limit.
async function rateLimit() {
  const { stdout } = await exec("gh", ["api", "rate_limit", "-q", ".resources.core"]);
  return JSON.parse(stdout);
}

let budget = await rateLimit();
let sinceCheck = 0;

// Keep a reserve so other tools sharing the token still work; re-read the real
// budget every 50 calls because concurrent workers and other clients spend it too.
async function throttle() {
  if (++sinceCheck >= 50 || budget.remaining < 200) {
    sinceCheck = 0;
    budget = await rateLimit();
  }
  budget.remaining--;
  if (budget.remaining < 100) {
    const wait = Math.max(0, budget.reset * 1000 - Date.now()) + 5000;
    console.error(`  rate limit nearly spent; sleeping ${Math.ceil(wait / 6e4)} min until reset`);
    await sleep(wait);
    budget = await rateLimit();
  }
}

async function api(path, attempt = 0) {
  await throttle();
  try {
    const { stdout } = await exec("gh", ["api", "--paginate", "--slurp", path], {
      maxBuffer: 1 << 28,
    });
    return JSON.parse(stdout);
  } catch (error) {
    const message = String(error.stderr || error.message);
    const limited = /rate limit|HTTP 403|HTTP 429|abuse|secondary/i.test(message);
    const transient = /HTTP 5\d\d|timeout|ECONNRESET|EOF/i.test(message);
    if ((!limited && !transient) || attempt >= 6) throw error;
    // Primary limit: wait for the reset. Secondary limit or 5xx: exponential backoff.
    budget = await rateLimit();
    const wait = budget.remaining === 0
      ? budget.reset * 1000 - Date.now() + 5000
      : Math.min(60_000 * 2 ** attempt, 15 * 60_000);
    console.error(`  ${limited ? "rate limited" : "transient error"} on ${path}; retrying in ${Math.ceil(wait / 1000)}s`);
    await sleep(wait);
    return api(path, attempt + 1);
  }
}

async function pool(items, size, fn) {
  const results = [];
  let next = 0;
  await Promise.all(
    Array.from({ length: size }, async () => {
      while (next < items.length) {
        const i = next++;
        results[i] = await fn(items[i]);
      }
    }),
  );
  return results;
}

const [repoInfo] = await api(`repos/${repo}`);

// A `created` filter returns at most 1,000 runs, so query one UTC day at a time
// and split a day into hours when it hits the cap.
async function runsIn(range) {
  const pages = await api(`repos/${repo}/actions/runs?per_page=100&created=${range}`);
  return { total: pages[0]?.total_count ?? 0, runs: pages.flatMap((page) => page.workflow_runs) };
}
const dates = Array.from({ length: days }, (_, i) =>
  new Date(Date.now() - i * 864e5).toISOString().slice(0, 10),
);
const runs = (
  await pool(dates, 4, async (date) => {
    const day = await runsIn(date);
    if (day.total <= 1000) return day.runs;
    const hours = await pool(Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0")), 4, (h) =>
      runsIn(`${date}T${h}:00:00Z..${date}T${h}:59:59Z`),
    );
    for (const [h, hour] of hours.entries())
      if (hour.total > 1000) console.error(`  warning: ${date} ${h}:00 has ${hour.total} runs; only 1,000 read`);
    return hours.flatMap((hour) => hour.runs);
  })
).flat();

// Finished runs never change, so their jobs are cached across invocations.
const cache = existsSync(cacheFile) ? JSON.parse(readFileSync(cacheFile, "utf8")) : {};
const saveCache = () => writeFileSync(cacheFile, JSON.stringify(cache));
process.on("SIGINT", () => {
  saveCache();
  process.exit(130);
});

// Skipped runs bill nothing; unfinished runs are not billed yet.
const toRead = runs.filter((r) => r.status === "completed" && r.conclusion !== "skipped");
const calls = toRead
  .filter((r) => !cache[`${r.id}/${r.run_attempt ?? 1}`])
  .reduce((n, r) => n + (r.run_attempt ?? 1), 0);
console.error(
  `${runs.length} runs in ${days} days; about ${calls} job requests needed, ${budget.remaining} left this hour`,
);

let done = 0;
const jobs = (
  await pool(toRead, 6, async (run) => {
    const key = `${run.id}/${run.run_attempt ?? 1}`;
    // Earlier attempts are billed too, so read every attempt of a rerun.
    cache[key] ??= (
      await Promise.all(
        Array.from({ length: run.run_attempt ?? 1 }, (_, a) =>
          api(`repos/${repo}/actions/runs/${run.id}/attempts/${a + 1}/jobs?per_page=100`),
        ),
      )
    )
      .flat()
      .flatMap((page) => page.jobs)
      .map((job) => ({
        job: job.name,
        conclusion: job.conclusion,
        labels: job.labels,
        runnerGroup: job.runner_group_name,
        startedAt: job.started_at,
        completedAt: job.completed_at,
      }));
    if (++done % 50 === 0) {
      console.error(`  ${done}/${toRead.length} runs`);
      saveCache();
    }
    return cache[key].map((job) => ({
      run: run.id,
      workflow: run.name,
      event: run.event,
      branch: run.head_branch,
      ...job,
    }));
  })
).flat();
saveCache();
if (outFile) writeFileSync(outFile, JSON.stringify(jobs));

const minutes = (j) => (new Date(j.completedAt) - new Date(j.startedAt)) / 6e4;
const ran = jobs.filter(
  (j) => j.conclusion !== "skipped" && j.startedAt && j.completedAt && minutes(j) > 0,
);
const standard = (j) => !j.runnerGroup || j.runnerGroup === "GitHub Actions";
const multiplier = (j) =>
  j.labels.some((l) => /^macos/i.test(l)) ? 10 : j.labels.some((l) => /^windows/i.test(l)) ? 2 : 1;
const billed = (j) => (standard(j) ? Math.ceil(minutes(j)) * multiplier(j) : 0);
const sum = (list, f) => list.reduce((total, j) => total + f(j), 0);
const round = (n) => Math.round(n).toLocaleString("en-US");
const pct = (n, of) => `${((100 * n) / (of || 1)).toFixed(1)}%`;
const quantile = (sorted, q) => sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];

const hosted = ran.filter(standard);
const total = sum(hosted, billed);
const raw = sum(hosted, (j) => minutes(j) * multiplier(j));
const other = ran.filter((j) => !standard(j));

console.log(`# GitHub Actions usage: ${repo}, last ${days} days\n`);
if (!repoInfo.private) {
  console.log("> Public repository: standard hosted runners are free here. Read the minutes below as runner time, not cost.\n");
}
console.log(`- Runs: ${runs.length}; jobs that ran: ${ran.length}`);
console.log(`- Billed minutes (standard hosted runners, Linux-minute equivalents): **${round(total)}** (about ${round((total * 30) / days)} a month)`);
console.log(`- Rounding each job up to a whole minute adds ${round(total - raw)} (${pct(total - raw, total)})`);
console.log(`- Cancelled jobs: ${round(sum(hosted.filter((j) => j.conclusion === "cancelled"), billed))} billed minutes; failed jobs: ${round(sum(hosted.filter((j) => j.conclusion === "failure"), billed))}`);
if (other.length) {
  const groups = [...new Set(other.map((j) => j.runnerGroup))].join(", ");
  console.log(`- Other runner groups (${groups}): ${round(sum(other, minutes))} minutes, not in the total. Self-hosted minutes are free; larger runners bill at their own rate.`);
}

const runsOf = new Map();
for (const r of runs) {
  const k = `${r.name} / ${r.event}`;
  runsOf.set(k, (runsOf.get(k) ?? 0) + 1);
}

// "Ran in" is the share of its workflow's runs (same event) that ran the job:
// near 100% on pull requests means its path filter matches almost everything.
function table(title, key, limit, ranIn) {
  const rows = new Map();
  for (const j of hosted) {
    const k = key(j);
    const row = rows.get(k) ?? { billed: 0, raw: 0, count: 0, runs: new Set(), of: `${j.workflow} / ${j.event}` };
    row.billed += billed(j);
    row.raw += minutes(j);
    row.count++;
    row.runs.add(j.run);
    rows.set(k, row);
  }
  console.log(`\n## ${title}\n`);
  console.log(ranIn
    ? "| Billed | Share | Jobs | Avg min | Ran in | Name |\n|---:|---:|---:|---:|---:|---|"
    : "| Billed | Share | Jobs | Avg min | Name |\n|---:|---:|---:|---:|---|");
  for (const [k, r] of [...rows].sort((a, b) => b[1].billed - a[1].billed).slice(0, limit)) {
    const share = ranIn ? ` ${pct(r.runs.size, runsOf.get(r.of))} |` : "";
    console.log(`| ${round(r.billed)} | ${pct(r.billed, total)} | ${r.count} | ${(r.raw / r.count).toFixed(1)} |${share} ${k} |`);
  }
}

table("By workflow and event", (j) => `${j.workflow} / ${j.event}`, 20, false);
table("Top jobs", (j) => `${j.workflow} / ${j.event} :: ${j.job.replace(/\s*\(.*\)$/, " (matrix)")}`, 30, true);

// Wall-clock time of successful runs, first attempt start to last update.
const durations = new Map();
for (const r of runs.filter((r) => r.conclusion === "success" && r.run_started_at)) {
  const k = `${r.name} / ${r.event}`;
  const list = durations.get(k) ?? [];
  list.push((new Date(r.updated_at) - new Date(r.run_started_at)) / 6e4);
  durations.set(k, list);
}
console.log("\n## Wall-clock time of successful runs\n");
console.log("| Runs | Median min | p90 min | Workflow / event |\n|---:|---:|---:|---|");
for (const [k, list] of [...durations].sort((a, b) => b[1].length - a[1].length).slice(0, 15)) {
  const sorted = list.sort((a, b) => a - b);
  console.log(`| ${sorted.length} | ${quantile(sorted, 0.5).toFixed(1)} | ${quantile(sorted, 0.9).toFixed(1)} | ${k} |`);
}

const prRuns = new Map();
for (const r of runs.filter((r) => r.event === "pull_request")) {
  const k = `${r.name} :: ${r.head_branch}`;
  prRuns.set(k, (prRuns.get(k) ?? 0) + 1);
}
if (prRuns.size) {
  const counts = [...prRuns.values()].sort((a, b) => a - b);
  console.log(`\n## Pull request churn\n\n- Runs per branch and workflow: median ${quantile(counts, 0.5)}, max ${counts.at(-1)} (${prRuns.size} branch/workflow pairs)`);
}
