import importlib.util
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).parents[2]
MATERIALIZER = ROOT / "check-contract" / "evals" / "materialize_fixture.py"


def _materializer():
    spec = importlib.util.spec_from_file_location(
        "check_contract_materializer",
        MATERIALIZER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@contextmanager
def materialized_repo(scenario: str, target: str = "target"):
    with tempfile.TemporaryDirectory() as temporary:
        destination = Path(temporary) / "scenario"
        result = _materializer().materialize(scenario, destination)
        yield Path(result["targets"][target]["destination"])


def packet_of(result):
    return json.loads(result.packet_path.read_text(encoding="utf-8"))
