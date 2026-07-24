import importlib.util
import math
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "replay_probe.py"
SPEC = importlib.util.spec_from_file_location("replay_probe", SCRIPT)
REPLAY_PROBE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(REPLAY_PROBE)

DESCRIPTOR = {
    "kind": "python-call-v1",
    "module": "src.pricing",
    "callable": "validate_percentage",
    "cases": [
        {"args": [0], "expect": "returns"},
        {"args": [100], "expect": "returns"},
        {
            "args": [-1],
            "expect": "raises",
            "exception": "ValueError",
        },
        {
            "args": [101],
            "expect": "raises",
            "exception": "ValueError",
        },
    ],
}


class ReplayProbeTests(unittest.TestCase):
    def test_parses_the_closed_python_call_v1_descriptor(self):
        probe = REPLAY_PROBE.parse_replay_probe(DESCRIPTOR)

        self.assertEqual(
            probe,
            REPLAY_PROBE.PythonCallProbe(
                module="src.pricing",
                callable="validate_percentage",
                cases=(
                    REPLAY_PROBE.PythonCallCase(
                        args=(0,),
                        expect="returns",
                        exception=None,
                    ),
                    REPLAY_PROBE.PythonCallCase(
                        args=(100,),
                        expect="returns",
                        exception=None,
                    ),
                    REPLAY_PROBE.PythonCallCase(
                        args=(-1,),
                        expect="raises",
                        exception="ValueError",
                    ),
                    REPLAY_PROBE.PythonCallCase(
                        args=(101,),
                        expect="raises",
                        exception="ValueError",
                    ),
                ),
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            probe.module = "changed"

    def test_rejects_unknown_kind_and_top_level_fields(self):
        invalid = {
            "unknown-kind": {**DESCRIPTOR, "kind": "python-call-v2"},
            "extra": {**DESCRIPTOR, "timeout": 1},
            "shell": {**DESCRIPTOR, "shell": "python -c 'pass'"},
            "argv": {**DESCRIPTOR, "argv": ["python", "-c", "pass"]},
        }

        for name, descriptor in invalid.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    REPLAY_PROBE.parse_replay_probe(descriptor)

    def test_rejects_non_identifier_module_and_callable_names(self):
        invalid = {
            "hyphenated-module": {
                **DESCRIPTOR,
                "module": "src.bad-name",
            },
            "empty-module-segment": {
                **DESCRIPTOR,
                "module": "src..pricing",
            },
            "module-keyword": {
                **DESCRIPTOR,
                "module": "src.class",
            },
            "hyphenated-callable": {
                **DESCRIPTOR,
                "callable": "validate-percentage",
            },
            "callable-keyword": {
                **DESCRIPTOR,
                "callable": "class",
            },
        }

        for name, descriptor in invalid.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    REPLAY_PROBE.parse_replay_probe(descriptor)

    def test_rejects_non_list_or_non_scalar_args(self):
        invalid_args = (
            (0,),
            [{"nested": "object"}],
            [[0]],
            [math.nan],
            [math.inf],
        )

        for args in invalid_args:
            descriptor = {
                **DESCRIPTOR,
                "cases": [{"args": args, "expect": "returns"}],
            }
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    REPLAY_PROBE.parse_replay_probe(descriptor)

    def test_rejects_unsupported_exception(self):
        descriptor = {
            **DESCRIPTOR,
            "cases": [
                {
                    "args": [-1],
                    "expect": "raises",
                    "exception": "TypeError",
                }
            ],
        }

        with self.assertRaises(ValueError):
            REPLAY_PROBE.parse_replay_probe(descriptor)

    def test_rejects_both_or_neither_expectation_shape(self):
        invalid_cases = {
            "both": {
                "args": [0],
                "expect": "returns",
                "exception": "ValueError",
            },
            "neither": {"args": [0], "expect": "unknown"},
            "raises-without-exception": {
                "args": [-1],
                "expect": "raises",
            },
        }

        for name, case in invalid_cases.items():
            descriptor = {**DESCRIPTOR, "cases": [case]}
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    REPLAY_PROBE.parse_replay_probe(descriptor)

    def test_rejects_unknown_case_fields_including_shell_and_argv(self):
        invalid_cases = {
            "extra": {"args": [0], "expect": "returns", "timeout": 1},
            "shell": {"args": [0], "expect": "returns", "shell": "true"},
            "argv": {"args": [0], "expect": "returns", "argv": ["true"]},
        }

        for name, case in invalid_cases.items():
            descriptor = {**DESCRIPTOR, "cases": [case]}
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    REPLAY_PROBE.parse_replay_probe(descriptor)

    def test_rejects_empty_case_list(self):
        descriptor = {**DESCRIPTOR, "cases": []}

        with self.assertRaisesRegex(ValueError, "at least one case"):
            REPLAY_PROBE.parse_replay_probe(descriptor)

    def test_rejects_duplicate_cases_after_parsing(self):
        descriptor = {
            **DESCRIPTOR,
            "cases": [
                {
                    "args": [-1],
                    "expect": "raises",
                    "exception": "ValueError",
                },
                {
                    "exception": "ValueError",
                    "expect": "raises",
                    "args": [-1],
                },
            ],
        }

        with self.assertRaisesRegex(ValueError, "duplicate case"):
            REPLAY_PROBE.parse_replay_probe(descriptor)

    def test_bool_and_numeric_cases_remain_distinct(self):
        descriptor = {
            **DESCRIPTOR,
            "cases": [
                {"args": [True], "expect": "returns"},
                {"args": [1], "expect": "returns"},
            ],
        }

        probe = REPLAY_PROBE.parse_replay_probe(descriptor)

        self.assertEqual(
            tuple(case.args for case in probe.cases),
            ((True,), (1,)),
        )
