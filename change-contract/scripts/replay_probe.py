import keyword
import math
from dataclasses import dataclass
from typing import TypeAlias


JSONScalar: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True)
class PythonCallCase:
    args: tuple[JSONScalar, ...]
    expect: str
    exception: str | None


@dataclass(frozen=True)
class PythonCallProbe:
    module: str
    callable: str
    cases: tuple[PythonCallCase, ...]


def _is_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.isidentifier()
        and not keyword.iskeyword(value)
    )


def _is_module_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and all(_is_identifier(part) for part in value.split("."))
    )


def _is_json_scalar(value: object) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _parse_case(value: object) -> PythonCallCase:
    if type(value) is not dict:
        raise ValueError("python-call-v1 case must be an object")

    expect = value.get("expect")
    expected_keys = (
        {"args", "expect"}
        if expect == "returns"
        else {"args", "expect", "exception"}
        if expect == "raises"
        else None
    )
    if expected_keys is None or set(value) != expected_keys:
        raise ValueError("invalid python-call-v1 expectation shape")
    if expect == "raises" and value["exception"] != "ValueError":
        raise ValueError("unsupported python-call-v1 exception")

    args = value["args"]
    if type(args) is not list or not all(_is_json_scalar(arg) for arg in args):
        raise ValueError("python-call-v1 args must be a list of JSON scalars")

    return PythonCallCase(
        args=tuple(args),
        expect=expect,
        exception=value.get("exception"),
    )


def parse_replay_probe(value: object) -> PythonCallProbe:
    if type(value) is not dict:
        raise ValueError("replay probe must be an object")
    if set(value) != {"kind", "module", "callable", "cases"}:
        raise ValueError("invalid replay probe fields")
    if value["kind"] != "python-call-v1":
        raise ValueError("unsupported replay probe kind")
    if not _is_module_name(value["module"]):
        raise ValueError("invalid python-call-v1 module")
    if not _is_identifier(value["callable"]):
        raise ValueError("invalid python-call-v1 callable")
    if type(value["cases"]) is not list:
        raise ValueError("python-call-v1 cases must be a list")

    return PythonCallProbe(
        module=value["module"],
        callable=value["callable"],
        cases=tuple(_parse_case(case) for case in value["cases"]),
    )
