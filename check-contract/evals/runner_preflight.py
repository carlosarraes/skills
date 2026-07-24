#!/usr/bin/env python3
import argparse
from pathlib import Path


ALLOWED_CONTROL_FILES = {"initial-state.json", "runner-prompt.txt"}
FORBIDDEN_CONTROL_TEXT = (
    '"assertions"',
    '"expected_output"',
    "expected verdict",
    "recommended route",
)


def validate_pre_run_directory(run_root: Path) -> None:
    root = run_root.resolve()
    if root.parent != Path("/tmp"):
        raise ValueError("baseline run root must be an opaque direct child of /tmp")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts[0] == "fixture":
            continue
        if relative.as_posix() not in ALLOWED_CONTROL_FILES:
            raise ValueError(f"unexpected pre-run control file: {relative}")
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in FORBIDDEN_CONTROL_TEXT:
            if forbidden.lower() in lowered:
                raise ValueError(
                    f"pre-run control file discloses grading data: {relative}"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    args = parser.parse_args()
    try:
        validate_pre_run_directory(args.run_root)
    except (OSError, ValueError) as error:
        print(str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
