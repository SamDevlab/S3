from __future__ import annotations

import pytest

from bootstrap.s3.ffi import FFIContract, FFIError, FFISignature, FFIType, validate_contract


def test_ffi_contract_is_explicit_and_confines_pointer_representation() -> None:
    signature = FFISignature("consume", (FFIType.BYTES_VIEW,), FFIType.I64)
    contract = validate_contract(signature)
    assert contract.calling_convention == "sysv-amd64"
    assert contract.payload["raw_pointers_contained"] is True
    assert contract.error_convention == "explicit-status"


def test_ffi_contract_rejects_uncontained_or_invalid_abi() -> None:
    with pytest.raises(FFIError, match="contained"):
        FFIContract(raw_pointers_contained=False)
    with pytest.raises(FFIError, match="version"):
        FFIContract(version="latest")
    signature = FFISignature("consume", (FFIType.BYTES_VIEW,), FFIType.I64)
    with pytest.raises(FFIError, match="call-scoped"):
        validate_contract(signature, FFIContract(buffer_convention="raw-pointer"))
