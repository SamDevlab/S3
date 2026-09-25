"""Deterministic references for S3 1.3 scientific benchmark workloads."""

from __future__ import annotations

import math
import sys


def score_size(length: int, seed: int = 0) -> int:
    left = [(-1.0, -0.5, 0.5, 1.0)[(index + seed) % 4] for index in range(length)]
    right = [value + 0.5 for value in left]
    total = sum(left)
    average = total / length
    spread = sum((value - average) ** 2 for value in left) / length
    self_product = sum(value * value for value in left)
    product = sum(a * b for a, b in zip(left, right, strict=True))
    squared = sum((a - b) ** 2 for a, b in zip(left, right, strict=True))
    euclidean = math.sqrt(squared)
    rmsd = math.sqrt(squared / length)
    magnitude = math.sqrt(self_product)
    if not (
        -0.01 < total < 0.01
        and -0.01 < average < 0.01
        and 0.62 < spread < 0.63
        and length * 0.6249 < self_product < length * 0.6251
        and length * 0.6249 < product < length * 0.6251
        and length * 0.2499 < squared < length * 0.2501
        and abs(euclidean - math.sqrt(length * 0.25)) < 0.01
        and 0.49 < rmsd < 0.51
        and math.sqrt(length * 0.6249) < magnitude < math.sqrt(length * 0.6251)
    ):
        return -1
    return length * 5 + 251


def run(seed: int = 0) -> int:
    return sum(
        score_size(length, seed + index)
        for index, length in enumerate((64, 256, 1024, 8192))
    )


def statistics_score_size(length: int) -> int:
    left = [(-1.0, -0.5, 0.5, 1.0)[index % 4] for index in range(length)]
    right = [value + 0.5 for value in left]
    average = sum(left) / length
    right_average = sum(right) / length
    spread = sum((value - average) ** 2 for value in left) / length
    deviation = math.sqrt(spread)
    covariance = sum(
        (a - average) * (b - right_average)
        for a, b in zip(left, right, strict=True)
    ) / length
    right_spread = sum((value - right_average) ** 2 for value in right) / length
    correlation = covariance / math.sqrt(spread * right_spread)
    if not (
        -0.01 < average < 0.01
        and 0.62 < spread < 0.63
        and 0.79 < deviation < 0.80
        and 0.62 < covariance < 0.63
        and 0.99 < correlation < 1.01
    ):
        return -1
    return length * 2 + 211


def statistics_run() -> int:
    return sum(
        statistics_score_size(length) for length in (64, 256, 1024, 8192)
    )


def similarity_distance_score_size(length: int) -> int:
    left = [(-1.0, -0.5, 0.5, 1.0)[index % 4] for index in range(length)]
    right = [value + 0.5 for value in left]
    squared = sum((a - b) ** 2 for a, b in zip(left, right, strict=True))
    euclidean = math.sqrt(squared)
    rmsd = math.sqrt(squared / length)
    mae = sum(abs(a - b) for a, b in zip(left, right, strict=True)) / length
    product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    cosine = product / (left_norm * right_norm)
    if not (
        abs(squared - length * 0.25) < 0.01
        and abs(euclidean - math.sqrt(length * 0.25)) < 0.01
        and 0.49 < rmsd < 0.51
        and 0.49 < mae < 0.51
        and abs(product - length * 0.625) < 0.01
        and 0.84 < cosine < 0.85
    ):
        return -1
    return length * 3 + 187


def similarity_distance_run() -> int:
    return sum(
        similarity_distance_score_size(length)
        for length in (64, 256, 1024, 8192)
    )


_WORKLOADS = {
    "science.structural-comparison.v1": run,
    "science.statistics-matrix.v1": statistics_run,
    "science.similarity-distance.v1": similarity_distance_run,
}


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in _WORKLOADS:
        raise SystemExit("unsupported benchmark invocation")
    repetitions = int(sys.argv[2])
    if repetitions <= 0:
        raise SystemExit("loops must be positive")
    result = 0
    for repetition in range(repetitions):
        result = (
            run(repetition)
            if sys.argv[1] == "science.structural-comparison.v1"
            else _WORKLOADS[sys.argv[1]]()
        )
    print(f"checksum={result}")
