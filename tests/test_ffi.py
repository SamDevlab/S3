from __future__ import annotations

import pytest

from bootstrap.s3.ffi import FFIError, FFISignature, FFIType, validate_signature


def test_ffi_signature_classifies_sysv_scalar_arguments() -> None:
    signature = FFISignature(
        "mix_values",
        (FFIType.I64, FFIType.F64, FFIType.TRYTE, FFIType.F64),
        FFIType.I64,
    )
    assert signature.integer_parameter_count == 2
    assert signature.float_parameter_count == 2
    assert signature.result.abi_class == "integer"
    assert validate_signature(signature) is signature


def test_ffi_rejects_invalid_symbols_and_non_scalar_contracts() -> None:
    with pytest.raises(FFIError, match="invalid external symbol"):
        FFISignature("puts@plt", (), FFIType.I64)
    with pytest.raises(FFIError, match="external result"):
        FFISignature("external", (), "i64")  # type: ignore[arg-type]
    with pytest.raises(FFIError, match="external parameters"):
        FFISignature("external", ("string",), FFIType.I64)  # type: ignore[arg-type]


def test_ffi_float_result_uses_float_abi_class() -> None:
    signature = FFISignature("read_value", (), FFIType.F64)
    assert signature.result.abi_class == "float"
