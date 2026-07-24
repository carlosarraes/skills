import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
PROTOCOL = ROOT.parent / "change-contract" / "references" / "contract-protocol.md"


def normalized(text):
    return " ".join(text.split())


def read_optional(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def section_from(text, heading):
    position = text.find(heading)
    return "" if position < 0 else text[position:]


class CheckContractSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = read_optional(SKILL)
        self.protocol = read_optional(PROTOCOL)
        self.check_protocol = section_from(
            self.protocol,
            "## Contract check vocabulary",
        )
        self.flat_skill = normalized(self.skill)
        self.flat_check_protocol = normalized(self.check_protocol)

    def assert_ordered(self, text, *phrases):
        positions = [text.find(phrase) for phrase in phrases]
        self.assertNotIn(-1, positions, phrases)
        self.assertEqual(positions, sorted(positions), phrases)

    def assert_no_unscoped_proven_absence_rule(self, text):
        self.assertNotIn(
            "proven absence is `unmet`.",
            normalized(text).lower(),
        )

    def test_is_explicitly_user_invoked_and_compact(self):
        self.assertTrue(self.skill.startswith("---\n"))
        frontmatter = self.skill.split("---", 2)[1]
        self.assertIn("name: check-contract", frontmatter)
        self.assertIn("disable-model-invocation: true", frontmatter)
        self.assertLessEqual(len(self.skill.split()), 900)

    def test_has_six_ordered_steps_with_completion_gates(self):
        headings = [
            "### Step 1: Resolve and verify authority",
            "### Step 2: Derive code-as-shipped first",
            "### Step 3: Classify contract fidelity",
            "### Step 4: Audit YAGNI and reuse",
            "### Step 5: Reconcile ledger and narrative",
            "### Step 6: Replace report and route",
        ]
        self.assert_ordered(self.skill, *headings)
        self.assertEqual(self.skill.count("### Step "), 6)
        self.assertEqual(self.skill.count("**Complete when:**"), 6)
        for start, end in zip(headings, headings[1:] + [None]):
            section = self.skill[self.skill.index(start):]
            if end:
                section = section[:section.index(end)]
            self.assertEqual(section.count("**Complete when:**"), 1)

    def test_reads_protocol_before_absolute_read_only_resolution(self):
        for phrase in (
            "Read the sibling protocol completely",
            "<change-contract-skill-dir>/references/contract-protocol.md",
            "absolute directory containing this loaded `SKILL.md`",
            "path inside the target repository",
            "resolve-consumer",
            "--allow-missing-ledger",
        ):
            self.assertIn(phrase, self.skill)
        self.assertNotIn(
            "python change-contract/scripts/contract_state.py",
            self.skill,
        )
        self.assert_ordered(
            self.skill,
            "Read the sibling protocol completely",
            "resolve-consumer",
        )
        self.assertRegex(
            self.skill,
            r"python <change-contract-skill-dir>/scripts/contract_state\.py "
            r"resolve-consumer[\s\\]+"
            r".*--repo <path-inside-target-repository>[\s\\]+"
            r".*--branch <full-branch>[\s\\]+"
            r".*--ticket <ticket>[\s\\]+"
            r".*--allow-missing-ledger",
        )

    def test_authority_resolution_is_complete_and_immutable(self):
        for phrase in (
            "canonical `git rev-parse --show-toplevel` root",
            ".notes/<branch-dir>/contract",
            "ai_docs/<branch-dir>/contract",
            "ambiguous",
            "orphaned",
            "true absence",
            "active version",
            "approval version",
            "full base",
            "full HEAD",
            "approval bytes",
            "approval SHA-256",
            "contract SHA-256",
            "branch",
            "ticket",
            "ancestry",
            "worktree state",
        ):
            self.assertIn(phrase.lower(), self.flat_skill.lower())
        self.assertIn(
            "Hard-stop true absence or any authority failure",
            self.flat_skill,
        )
        self.assertIn(
            "preserve any existing report",
            self.flat_skill,
        )

    def test_code_first_order_precedes_ledger_and_narrative(self):
        self.assert_ordered(
            self.skill,
            "### Step 2: Derive code-as-shipped first",
            "### Step 3: Classify contract fidelity",
            "### Step 4: Audit YAGNI and reuse",
            "### Step 5: Reconcile ledger and narrative",
        )
        step_two = self.skill[
            self.skill.index("### Step 2:"):
            self.skill.index("### Step 3:")
        ]
        for phrase in (
            "`git diff <base>..<full-head> -- "
            "<implementation-source/test-paths>`",
            "renames",
            "contract artifacts",
            "changed source/tests",
            "surrounding code",
            "public contracts",
            "side effects",
            "persisted state",
            "integrations",
            "`file:line`",
        ):
            self.assertIn(normalized(phrase), normalized(step_two))
        self.assertIn(
            normalized(
                "Do not read the contents of changed contract artifacts"
            ),
            normalized(step_two),
        )

    def test_all_clause_families_and_axes_are_classified(self):
        for token in (
            "Outcome",
            "B/N/I/C/R",
            "expected-surface",
            "complexity-budget",
            "acceptance-evidence",
            "Contract fidelity",
            "YAGNI",
            "Reuse",
            "Documented drift",
            "Undocumented drift",
        ):
            self.assertIn(token, self.skill)
        self.assertIn(
            "Clause status: `MET | UNMET | EXCEEDED | INDETERMINATE`",
            self.check_protocol,
        )
        self.assertIn(
            "Ledger status: `VERIFIED | QUESTIONABLE | CONTRADICTED`",
            self.check_protocol,
        )

    def test_code_as_shipped_uses_only_recorded_head_git_objects(self):
        step_two = section_from(
            self.skill,
            "### Step 2: Derive code-as-shipped first",
        )
        if "### Step 3:" in step_two:
            step_two = step_two.split("### Step 3:", 1)[0]
        for phrase in (
            "`git diff <base>..<full-head> -- "
            "<implementation-source/test-paths>`",
            "`git show <full-head>:<path>`",
            "every code-as-shipped byte",
            "Git object",
            "source Git-object IDs",
            "dirty worktree",
            "non-authoritative limitation",
        ):
            self.assertIn(normalized(phrase), normalized(step_two))
        self.assert_ordered(
            step_two,
            "`git diff <base>..<full-head> -- "
            "<implementation-source/test-paths>`",
            "`git show <full-head>:<path>`",
        )

    def test_evidence_collection_has_executable_caps_and_stop_rule(self):
        step_two = self.skill[
            self.skill.index("### Step 2:"):
            self.skill.index("### Step 3:")
        ]
        step_five = self.skill[
            self.skill.index("### Step 5:"):
            self.skill.index("### Step 6:")
        ]
        required = (
            "record the monotonic start",
            "start plus 180 seconds",
            "caller deadline minus a 60-second finalization reserve",
            "exactly one name inventory",
            "one batched recorded-HEAD implementation read",
            "one batched repository-wide responsibility/reuse search",
            "never reread, retry, or issue per-path or per-responsibility queries",
            "three batches finish, immediately freeze the code-as-shipped "
            "account",
            "evidence deadline arrives first, stop evidence collection",
            "mark every uncollected clause or search result `INDETERMINATE`",
            "proceed through Steps 3-6",
            "reserve at least 60 seconds for Steps 5-6",
        )
        for phrase in required:
            self.assertIn(normalized(phrase), normalized(step_two))
        self.assert_ordered(
            normalized(step_two),
            *[normalized(phrase) for phrase in required],
        )
        for phrase in (
            "D-stated replay probe",
            "complete stated probe",
            "disposable temporary tree outside the target repository",
            "`git archive <full-head>`",
            "`PYTHONDONTWRITEBYTECODE=1`",
            "remove the temporary tree",
            "never mutate the target",
        ):
            self.assertIn(normalized(phrase), normalized(step_five))

    def test_compound_a_hard_stop_is_a_strict_phase_boundary(self):
        heading = "## Compound A-then-B boundary"
        self.assertEqual(self.skill.count(heading), 1)
        compound = self.skill[
            self.skill.index(heading):
            self.skill.index("### Step 1:")
        ]
        required = (
            "For a compound A-then-B request",
            "hash A's existing report sentinel as opaque bytes without parsing",
            "resolve A",
            "complete A's failed-authority, zero-write, and "
            "sentinel-preservation attestation before any B repository action",
            "resolve B independently",
            "After any B repository action begins, run no command against A, "
            "read no A path, and make no later path reference to A",
        )
        for phrase in required:
            self.assertIn(normalized(phrase), normalized(compound))
        self.assert_ordered(
            normalized(compound),
            *[normalized(phrase) for phrase in required],
        )
        remainder = self.skill[self.skill.index("### Step 1:"):]
        for prohibited in (
            "command against A",
            "read no A path",
            "path reference to A",
            "access or mutate A",
        ):
            self.assertNotIn(
                normalized(prohibited),
                normalized(remainder),
            )

    def test_code_first_freezes_before_approved_contract_and_narratives(self):
        step_two = self.skill[
            self.skill.index("### Step 2:"):
            self.skill.index("### Step 3:")
        ]
        for phrase in (
            "inventory names first",
            "`git diff --name-status --find-renames <base>..<full-head>`",
            "path-filtered Git-object operations",
            "implementation source and tests only",
            "Do not read the contents of changed contract artifacts, the "
            "active ledger, prior report, supplied or worker summaries, PR "
            "narratives, or other author narratives yet",
            "freeze the code-as-shipped account",
            "read the immutable approved contract body from the verified "
            "`contract_path` bytes",
        ):
            self.assertIn(normalized(phrase), normalized(step_two))
        self.assertNotIn(
            "defer the contents of contract artifacts",
            normalized(step_two),
        )
        self.assert_ordered(
            normalized(self.skill),
            normalized("implementation source and tests only"),
            normalized("freeze the code-as-shipped account"),
            normalized(
                "read the immutable approved contract body from the verified "
                "`contract_path` bytes"
            ),
            normalized("### Step 3: Classify contract fidelity"),
            normalized("### Step 5: Reconcile ledger and narrative"),
            normalized("Only now read the guarded active ledger"),
        )

    def test_acceptance_rows_prove_exact_predicates_without_axis_leakage(self):
        for phrase in (
            "Emit one explicit `A-<B-id>` row for every B",
            "evidence demonstrates the exact mapped B predicate",
            "An adjacent behavior, happy path, or non-boundary example",
            "missing or non-demonstrative evidence is `INDETERMINATE`",
            "Judge each clause's exact approved predicate",
            "do not substitute a broader or narrower implementation proxy",
            "Implementation path, expected surface, reuse, simplicity, and "
            "complexity-budget facts do not alter an Outcome/B clause status",
            "dedicated axes",
        ):
            self.assertIn(phrase, self.flat_check_protocol)
        for fixture_specific in ("class hierarchy", "private class"):
            self.assertNotIn(fixture_specific, self.flat_check_protocol)

    def test_yagni_requires_an_evidenced_unearned_added_construct(self):
        required = (
            "YAGNI requires an evidenced unearned added construct",
            "Correctness defects, missing tests, deletions, unexpected surface, "
            "and complexity-budget excess alone do not establish YAGNI",
            "A budget excess affects YAGNI only when the added construct is "
            "proven unearned",
        )
        for phrase in required:
            self.assertIn(phrase, self.flat_check_protocol)
        self.assertNotIn(
            "violates a numeric complexity budget of zero",
            self.flat_check_protocol,
        )

    def test_reuse_pass_requires_full_head_full_tree_search_evidence(self):
        step_two = self.skill[
            self.skill.index("### Step 2:"):
            self.skill.index("### Step 3:")
        ]
        step_four = self.skill[
            self.skill.index("### Step 4:"):
            self.skill.index("### Step 5:")
        ]
        for phrase in (
            "one batched repository-wide responsibility/reuse search",
            "Use the batched recorded full-HEAD full-tree search evidence",
            "every changed responsibility",
            "before Reuse can be `PASS`",
            "missing search evidence cannot yield `PASS`",
            "compatible helper",
            "duplicated or bypassed",
            "Reuse `FAIL`",
        ):
            if "repository-wide" in phrase:
                source = step_two
            elif "full-tree" in phrase:
                source = step_four
            else:
                source = self.check_protocol
            self.assertIn(normalized(phrase), normalized(source))
        self.assertNotIn(
            "Perform a recorded full-HEAD full-tree search",
            step_four,
        )

    def test_head_only_rule_is_implementation_scoped(self):
        step_two = self.skill[
            self.skill.index("### Step 2:"):
            self.skill.index("### Step 3:")
        ]
        step_five = self.skill[
            self.skill.index("### Step 5:"):
            self.skill.index("### Step 6:")
        ]
        self.assertIn(
            normalized(
                "Later implementation/code reads and searches use recorded "
                "full-HEAD objects, never worktree files"
            ),
            normalized(step_two),
        )
        self.assertNotIn(
            normalized(
                "Later reads and searches use recorded full-HEAD objects"
            ),
            normalized(step_two),
        )
        self.assertIn(
            normalized(
                "read the guarded active ledger, prior report, supplied "
                "summary, PR claims, and other narratives from their guarded "
                "sources"
            ),
            normalized(step_five),
        )

    def test_ledger_verification_is_factual_and_chronological(self):
        for phrase in (
            "complete factual fields, commit chronology, and replay-probe "
            "evidence",
            "A compatible helper that exists before the affected "
            "implementation commit qualifies as pre-existing",
            "same author",
            "created after contract approval",
            "Motive or authorship speculation alone cannot make a D entry "
            "`CONTRADICTED`",
        ):
            self.assertIn(phrase, self.flat_check_protocol)

    def test_skill_does_not_duplicate_protocol_owned_enumerations(self):
        self.assertIn(
            "protocol-defined clause status",
            self.skill,
        )
        for enumeration in (
            "MET | UNMET | EXCEEDED | INDETERMINATE",
            "VERIFIED | QUESTIONABLE | CONTRADICTED",
            "PASS | PARTIAL | FAIL",
            "PASS | WARNING | FAIL",
            "NONE | ACCEPTED | QUESTIONABLE",
            "NONE | PRESENT",
            "PASS | PASS WITH DOCUMENTED DRIFT",
        ):
            self.assertNotIn(enumeration, self.skill)

    def test_protocol_defines_total_clause_and_ledger_semantics(self):
        for phrase in (
            "For positive clauses (O/B/I/C/R/A)",
            "For non-goals (N)",
            "For expected-surface clauses (S)",
            "For complexity-budget clauses (K)",
            "`INDETERMINATE` means",
            "`VERIFIED` means",
            "`QUESTIONABLE` means",
            "`CONTRADICTED` means",
            "A fidelity-owned `EXCEEDED` that does not change an approved "
            "behavior, public contract, or risk boundary",
            "two or more localized items are proven unearned",
            "one or more questionable localized items",
            "when no F/U/D IDs exist, state `IDs: none`",
        ):
            self.assertIn(phrase, self.flat_check_protocol)

    def test_protocol_disambiguates_absence_and_non_goal_exceeded(self):
        required = (
            "For non-goals (N), `MET` means the excluded behavior is absent",
            "`EXCEEDED` requires evidence that the implementation actively "
            "imposes an additional restriction on existing or approved "
            "behavior",
            "ordinary non-implementation or absence of arbitrary unrequested "
            "behavior is `MET`, not `EXCEEDED`",
            "Negative C predicates such as `C1: None` use the non-goal absence "
            "semantics: `MET` when the declared-absent contract or side effect "
            "is absent and `UNMET` when it is present",
            "Family-specific rules take precedence over the general absence "
            "rule",
            "N clauses and negative C predicates such as `C1: None` cannot be "
            "inverted by that general rule",
            "Proven absence is `UNMET` only for a required positive predicate "
            "or required item",
        )
        for phrase in required:
            self.assertIn(phrase, self.flat_check_protocol)
        self.assert_ordered(
            self.flat_check_protocol,
            required[0],
            required[1],
            required[2],
            required[3],
            required[4],
            required[5],
            required[6],
        )
        self.assert_no_unscoped_proven_absence_rule(
            self.flat_check_protocol,
        )

    def test_absence_regression_guard_rejects_original_uppercase_sentence(self):
        with self.assertRaises(AssertionError):
            self.assert_no_unscoped_proven_absence_rule(
                "Proven absence is `UNMET`."
            )

    def test_protocol_owns_exact_taxonomy_aggregation_and_precedence(self):
        required = (
            "Contract fidelity: `PASS | PARTIAL | FAIL`",
            "YAGNI: `PASS | WARNING | FAIL`",
            "Reuse: `PASS | WARNING | FAIL`",
            "Documented drift: `NONE | ACCEPTED | QUESTIONABLE`",
            "Undocumented drift: `NONE | PRESENT`",
            "Overall verdict: `PASS | PASS WITH DOCUMENTED DRIFT | NEEDS HUMAN "
            "REVIEW | CONTRACT VIOLATED`",
            "Recommended next skill: `<ordered route>`",
            "Contract fidelity owns Outcome, B/N/I/C clauses",
            "YAGNI `FAIL`",
            "YAGNI `WARNING`",
            "Reuse `FAIL`",
            "Reuse `WARNING`",
            "Documented drift `NONE`",
            "Documented drift `ACCEPTED`",
            "Documented drift `QUESTIONABLE`",
            "Undocumented drift `PRESENT`",
            "Apply this exhaustive precedence after authority succeeds",
        )
        for phrase in required:
            self.assertIn(phrase, self.flat_check_protocol)
        self.assertRegex(
            self.check_protocol,
            r"\| 1 \|.*CONTRACT VIOLATED.*change-contract.*\n"
            r"\| 2 \|.*CONTRACT VIOLATED.*exec-ticket.*clean-up.*\n"
            r"\| 3 \|.*CONTRACT VIOLATED.*exec-ticket.*\n"
            r"\| 4 \|.*NEEDS HUMAN REVIEW.*clean-up.*\n"
            r"\| 5 \|.*NEEDS HUMAN REVIEW.*qa-ticket.*\n"
            r"\| 6 \|.*NEEDS HUMAN REVIEW.*clean-up.*\n"
            r"\| 7 \|.*PASS WITH DOCUMENTED DRIFT.*qa-pr.*qa-ticket.*\n"
            r"\| 8 \|.*PASS.*qa-pr.*qa-ticket",
        )

    def test_protocol_owns_routes_and_stable_ids(self):
        for row in (
            "| Missing/incorrect behavior | `exec-ticket` |",
            "| Correct behavior plus duplication/bloat/missed reuse | `clean-up` |",
            "| Correctness and simplicity | `exec-ticket`, then `clean-up` |",
            "| Contract obsolete/wrong | `change-contract` for a new human-approved version |",
            "| Contract satisfied and lean | `qa-ticket` |",
            "| Acceptance QA exists and review evidence is needed | `qa-pr` |",
        ):
            self.assertIn(row, self.check_protocol)
        for phrase in (
            "`O1` for Outcome",
            "preserve authored `B*`, `N*`, `I*`, `C*`, and `R*`",
            "`S1..Sn`",
            "`K-MODULES`",
            "`K-DEPENDENCIES`",
            "`K-ABSTRACTIONS`",
            "`K-CONFIGURATION`",
            "`K-PUBLIC-INTERFACES`",
            "`A-<B-id>`",
            "preserve `D1..Dn`",
            "`U1..Un`",
            "`F1..Fn`",
            "when no F/U/D IDs exist, state `IDs: none`",
        ):
            self.assertIn(normalized(phrase), normalized(self.check_protocol))

    def test_report_shape_and_rows_are_fixed(self):
        headings = (
            "# Contract Check: <ticket> — v<version>",
            "Audit range: <full-base>..<full-head>",
            "Worktree state: <clean or limitation>",
            "Contract SHA-256: <digest>",
            "## Code-first observed behavior",
            "## Clause-by-clause fidelity",
            "## YAGNI and reuse",
            "## Drift reconciliation",
            "## Ordered findings",
            "## Verdict and route",
            "<exact verdict block>",
            "## Mutation attestation",
        )
        self.assert_ordered(self.skill, *headings)
        self.assertIn(
            "Clause rows contain ID, status, evidence, and reason",
            self.flat_skill,
        )
        self.assertIn(
            "Drift rows contain D/deviation ID, status, evidence, and documentation state",
            self.flat_skill,
        )
        self.assertIn("stable finding IDs", self.flat_skill)

    def test_final_resolution_and_atomic_replacement_are_adjacent(self):
        step_six = section_from(
            self.skill,
            "### Step 6: Replace report and route",
        )
        self.assertRegex(
            normalized(step_six).lower(),
            r"render the complete report outside the repository\. Immediately "
            r"rerun .*resolve-consumer.* require equality of the canonical "
            r"root, full HEAD, active version, approval bytes and SHA-256, "
            r"contract SHA-256, full base, branch/ticket identity, and ancestry\."
            .lower(),
        )
        self.assert_ordered(
            step_six,
            "Immediately rerun",
            "Atomically create or replace",
        )
        for phrase in (
            "source",
            "contract",
            "ledger",
            "status",
            "prior report",
            "supplied-narrative",
            "guarded hashes",
            "freshness mismatch",
            "preserve the previous report",
            "no other audit-caused final delta",
        ):
            self.assertIn(normalized(phrase), normalized(step_six))
        self.assert_ordered(
            step_six,
            "supplied-narrative",
            "Atomically create or replace",
        )

    def test_only_report_mutation_and_routes_are_advisory(self):
        for phrase in (
            "The only permitted repository mutation is atomic replacement",
            "still-active `check-report.md`",
            "Do not fix code",
            "Do not edit the contract or ledger",
            "Do not post",
            "Do not commit",
            "Do not push",
            "Do not approve",
            "Do not invoke the recommended skill",
            "Routes are advisory only",
        ):
            self.assertIn(normalized(phrase).lower(), self.flat_skill.lower())


if __name__ == "__main__":
    unittest.main()
