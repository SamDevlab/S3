"""Deterministic R3 differential orchestration for Reliability Lab v2."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

from tools.reliability_contract_v2 import (
    DEFAULT_RESOURCE_POLICY,
    REPLAY_SCHEMA,
    canonical_json_document,
    sha256_hex,
    validate_failure_signature,
)
from tools.reliability_generator_v2 import GeneratedCase, generate_cases
from tools.reliability_runner_v2 import IsolatedRunResult, run_isolated_worker

R3_CAMPAIGN_SCHEMA = "s3.reliability.differential-campaign.v1"
R3_CASE_SCHEMA = "s3.reliability.differential-case.v1"
R3_REPLAY_VERSION = "s3.reliability.replay.v2-r3"
R3_NATIVE_WORKER = (sys.executable, "-m", "tools.reliability_worker_r3")
CONFIRMATION_RUNS = 2
MAX_NATIVE_CASES = 32

Executor = Callable[[Mapping[str, object], bool], IsolatedRunResult]


@dataclass(frozen=True, slots=True)
class PathObservation:
    label: str
    backend: str
    optimization: str
    worker_status: str
    response_status: str | None
    result_sha256: str | None
    failure_signature: str | None

    def stable_key(self) -> tuple[object, ...]:
        return (
            self.worker_status,
            self.response_status,
            self.result_sha256,
            self.failure_signature,
        )


@dataclass(frozen=True, slots=True)
class DifferentialResult:
    schema: str
    case_id: str
    case_index: int
    family: str
    outcome: str
    failure_signature: str | None
    native_selected: bool
    observations: tuple[PathObservation, ...]
    confirmation_runs: int
    replay_path: str | None

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["observations"] = [asdict(item) for item in self.observations]
        return value


def _default_executor(request: Mapping[str, object], native: bool) -> IsolatedRunResult:
    return run_isolated_worker(
        request,
        worker_argv=R3_NATIVE_WORKER if native else None,
    )


def _observe(
    case: GeneratedCase,
    compiler_head: str,
    *,
    backend: str,
    optimization: str,
    executor: Executor,
) -> PathObservation:
    native = backend == "linux-x86_64-native"
    request = case.worker_request(
        compiler_head,
        operation="RUN_NATIVE" if native else "RUN_HOSTED",
        optimization=optimization,
        backend=backend,
    )
    result = executor(request, native)
    if result.status != "RESPONSE":
        return PathObservation(
            label=f"{backend}:{optimization}",
            backend=backend,
            optimization=optimization,
            worker_status=result.status,
            response_status=None,
            result_sha256=None,
            failure_signature=result.failure_signature,
        )
    response = result.response
    if response is None:
        return PathObservation(
            label=f"{backend}:{optimization}",
            backend=backend,
            optimization=optimization,
            worker_status="HARNESS_ERROR",
            response_status=None,
            result_sha256=None,
            failure_signature="harness-error:missing-response",
        )
    response_status = str(response["status"])
    result_sha = response.get("result_sha256")
    return PathObservation(
        label=f"{backend}:{optimization}",
        backend=backend,
        optimization=optimization,
        worker_status="RESPONSE",
        response_status=response_status,
        result_sha256=result_sha if isinstance(result_sha, str) else None,
        failure_signature=None,
    )


def _single_path_outcome(observation: PathObservation) -> tuple[str, str | None]:
    if observation.worker_status == "TIMEOUT":
        return "TIMEOUT", observation.failure_signature
    if observation.worker_status == "CRASH":
        return "CRASH", observation.failure_signature
    if observation.worker_status == "RESOURCE_LIMIT":
        return "RESOURCE_LIMIT", observation.failure_signature
    if observation.worker_status != "RESPONSE":
        return "HARNESS_ERROR", observation.failure_signature or "harness-error:worker"
    if observation.response_status == "REJECTED":
        return (
            "UNEXPECTED_REJECTION",
            f"unexpected-rejection:{observation.label}",
        )
    if observation.response_status != "COMPLETED" or observation.result_sha256 is None:
        return "HARNESS_ERROR", f"harness-error:invalid-completed:{observation.label}"
    return "PASS", None


def _confirm_stability(
    case: GeneratedCase,
    compiler_head: str,
    observations: tuple[PathObservation, ...],
    *,
    executor: Executor,
) -> tuple[bool, tuple[PathObservation, ...]]:
    repeated: list[PathObservation] = []
    for original in observations:
        for _ in range(CONFIRMATION_RUNS):
            repeated.append(
                _observe(
                    case,
                    compiler_head,
                    backend=original.backend,
                    optimization=original.optimization,
                    executor=executor,
                )
            )
    stable = True
    offset = 0
    for original in observations:
        for candidate in repeated[offset : offset + CONFIRMATION_RUNS]:
            if candidate.stable_key() != original.stable_key():
                stable = False
        offset += CONFIRMATION_RUNS
    return stable, tuple(repeated)


def _evaluate_matrix(
    case: GeneratedCase,
    compiler_head: str,
    observations: tuple[PathObservation, ...],
    *,
    executor: Executor,
) -> tuple[str, str | None, tuple[PathObservation, ...], int]:
    for observation in observations:
        outcome, signature = _single_path_outcome(observation)
        if outcome != "PASS":
            stable, confirmations = _confirm_stability(
                case,
                compiler_head,
                (observation,),
                executor=executor,
            )
            if not stable:
                return (
                    "NONDETERMINISM",
                    f"nondeterminism:{observation.label}",
                    observations + confirmations,
                    len(confirmations),
                )
            validate_failure_signature(outcome, signature)
            return outcome, signature, observations + confirmations, len(confirmations)

    result_hashes = {observation.result_sha256 for observation in observations}
    if len(result_hashes) == 1:
        return "PASS", None, observations, 0

    stable, confirmations = _confirm_stability(
        case,
        compiler_head,
        observations,
        executor=executor,
    )
    if not stable:
        signature = "nondeterminism:differential-matrix"
        validate_failure_signature("NONDETERMINISM", signature)
        return (
            "NONDETERMINISM",
            signature,
            observations + confirmations,
            len(confirmations),
        )
    signature = "miscompile:" + ":".join(
        f"{item.label}={item.result_sha256}" for item in observations
    )
    if len(signature) > 512:
        signature = "miscompile:matrix:" + sha256_hex(signature.encode("ascii"))
    validate_failure_signature("MISCOMPILE", signature)
    return "MISCOMPILE", signature, observations + confirmations, len(confirmations)


def _write_replay_bundle(
    root: Path,
    case: GeneratedCase,
    compiler_head: str,
    outcome: str,
    signature: str,
    observations: tuple[PathObservation, ...],
) -> str:
    bundle = root / case.case_id
    bundle.mkdir(parents=True, exist_ok=False)
    source_path = bundle / "input.s3"
    metadata_path = bundle / "metadata.json"
    result_path = bundle / "result.json"
    replay_path = bundle / "replay.json"

    source_path.write_bytes(case.source)
    metadata_path.write_bytes(canonical_json_document(case.metadata()))
    result_payload = {
        "schema": R3_CASE_SCHEMA,
        "case_id": case.case_id,
        "outcome": outcome,
        "failure_signature": signature,
        "observations": [asdict(item) for item in observations],
    }
    result_path.write_bytes(canonical_json_document(result_payload))
    replay_payload = {
        "schema": REPLAY_SCHEMA,
        "replay_version": R3_REPLAY_VERSION,
        "case_id": case.case_id,
        "compiler_head": compiler_head,
        "source_path": "input.s3",
        "source_sha256": case.source_sha256,
        "metadata_path": "metadata.json",
        "metadata_sha256": sha256_hex(metadata_path.read_bytes()),
        "result_path": "result.json",
        "result_sha256": sha256_hex(result_path.read_bytes()),
        "expected_failure_signature": signature,
    }
    encoded = canonical_json_document(replay_payload)
    projected_size = (
        len(case.source)
        + metadata_path.stat().st_size
        + result_path.stat().st_size
        + len(encoded)
    )
    if projected_size > DEFAULT_RESOURCE_POLICY.replay_bundle_max_bytes:
        raise ValueError("replay bundle exceeds frozen replay_bundle_max_bytes")
    replay_path.write_bytes(encoded)
    return bundle.name


def run_case(
    case: GeneratedCase,
    compiler_head: str,
    *,
    native: bool,
    replay_root: Path | None = None,
    executor: Executor = _default_executor,
) -> DifferentialResult:
    if case.case_kind != "valid":
        raise ValueError("R3 differential execution accepts valid generated cases only")

    observations = (
        _observe(
            case,
            compiler_head,
            backend="hosted",
            optimization="O0",
            executor=executor,
        ),
        _observe(
            case,
            compiler_head,
            backend="hosted",
            optimization="O1",
            executor=executor,
        ),
    )
    if native:
        observations += (
            _observe(
                case,
                compiler_head,
                backend="linux-x86_64-native",
                optimization="O0",
                executor=executor,
            ),
            _observe(
                case,
                compiler_head,
                backend="linux-x86_64-native",
                optimization="O1",
                executor=executor,
            ),
        )

    outcome, signature, all_observations, confirmation_runs = _evaluate_matrix(
        case,
        compiler_head,
        observations,
        executor=executor,
    )
    replay_path: str | None = None
    if outcome != "PASS":
        assert signature is not None
        validate_failure_signature(outcome, signature)
        if replay_root is not None:
            replay_path = _write_replay_bundle(
                replay_root,
                case,
                compiler_head,
                outcome,
                signature,
                all_observations,
            )
    return DifferentialResult(
        schema=R3_CASE_SCHEMA,
        case_id=case.case_id,
        case_index=case.case_index,
        family=case.family,
        outcome=outcome,
        failure_signature=signature,
        native_selected=native,
        observations=all_observations,
        confirmation_runs=confirmation_runs,
        replay_path=replay_path,
    )


def run_campaign(
    campaign_id: str,
    campaign_seed: int,
    compiler_head: str,
    *,
    case_count: int,
    native_case_count: int = 0,
    replay_root: Path | None = None,
    executor: Executor = _default_executor,
) -> dict[str, object]:
    if isinstance(case_count, bool) or not isinstance(case_count, int) or case_count < 1:
        raise ValueError("case_count must be a positive integer")
    if case_count > DEFAULT_RESOURCE_POLICY.campaign_max_cases:
        raise ValueError("case_count exceeds frozen campaign_max_cases")
    if (
        isinstance(native_case_count, bool)
        or not isinstance(native_case_count, int)
        or native_case_count < 0
        or native_case_count > min(case_count, MAX_NATIVE_CASES)
    ):
        raise ValueError("native_case_count exceeds bounded R3 native shard")

    cases = generate_cases(campaign_id, campaign_seed, "valid", case_count)
    results: list[DifferentialResult] = []
    for index, case in enumerate(cases):
        results.append(
            run_case(
                case,
                compiler_head,
                native=index < native_case_count,
                replay_root=replay_root,
                executor=executor,
            )
        )

    counts: dict[str, int] = {}
    for result in results:
        counts[result.outcome] = counts.get(result.outcome, 0) + 1
    return {
        "schema": R3_CAMPAIGN_SCHEMA,
        "campaign_id": campaign_id,
        "campaign_seed": campaign_seed,
        "compiler_head": compiler_head,
        "case_count": len(results),
        "native_case_count": native_case_count,
        "confirmation_runs_per_path": CONFIRMATION_RUNS,
        "counts": {key: counts[key] for key in sorted(counts)},
        "results": [result.to_dict() for result in results],
    }


def write_campaign_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_document(dict(report)))


def load_replay(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != REPLAY_SCHEMA:
        raise ValueError("invalid R3 replay manifest")
    return value
