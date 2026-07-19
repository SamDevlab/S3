import pytest
import random
from tools.segmented_bigint import Base300BigInt, BinaryLimbBigInt

def test_base300_canonical_zero():
    z1 = Base300BigInt()
    z2 = Base300BigInt([0, 0, 0])
    assert z1.limbs == [0]
    assert z2.limbs == [0]

def test_base300_conversion():
    vals = [0, 1, 299, 300, 301, 300*300 - 1, 123456789]
    for v in vals:
        b = Base300BigInt.from_int(v)
        assert b.to_int() == v

def test_base300_add_sub():
    v1 = 123456
    v2 = 78901
    b1 = Base300BigInt.from_int(v1)
    b2 = Base300BigInt.from_int(v2)
    b3, _ = b1.add(b2)
    assert b3.to_int() == v1 + v2
    
    b4, _ = b1.sub(b2)
    assert b4.to_int() == v1 - v2
    
def test_base300_square():
    v = 123456789
    b = Base300BigInt.from_int(v)
    b2 = b.square()
    assert b2.to_int() == v * v

def test_binary_limb_canonical_zero():
    z1 = BinaryLimbBigInt()
    z2 = BinaryLimbBigInt([0, 0, 0])
    assert z1.limbs == [0]
    assert z2.limbs == [0]

def test_binary_limb_conversion():
    vals = [0, 1, (1<<30)-1, 1<<30, (1<<30)+1, (1<<60)-1, 123456789123456789]
    for v in vals:
        b = BinaryLimbBigInt.from_int(v)
        assert b.to_int() == v

def test_binary_limb_add_sub():
    v1 = 123456789123456789
    v2 = 98765432198765432
    b1 = BinaryLimbBigInt.from_int(v1)
    b2 = BinaryLimbBigInt.from_int(v2)
    b3, _ = b1.add(b2)
    assert b3.to_int() == v1 + v2
    
    b4, _ = b1.sub(b2)
    assert b4.to_int() == v1 - v2

def test_binary_limb_square():
    random.seed(42)
    v = random.randint(10**50, 10**60)
    b = BinaryLimbBigInt.from_int(v)
    b2 = b.square()
    assert b2.to_int() == v * v

def test_binary_limb_mersenne_reduce():
    p = 17
    mod = (1 << p) - 1
    v = (1 << (2*p)) - 12345
    b = BinaryLimbBigInt.from_int(v)
    b_red = b.mersenne_reduce(p)
    assert b_red.to_int() == v % mod

def test_binary_limb_mersenne_reduce_exact():
    p = 19
    mod = (1 << p) - 1
    # Test multiple of M_p
    v = mod * 5
    b = BinaryLimbBigInt.from_int(v)
    b_red = b.mersenne_reduce(p)
    assert b_red.to_int() == 0

    # Test exactly M_p
    b = BinaryLimbBigInt.from_int(mod)
    b_red = b.mersenne_reduce(p)
    assert b_red.to_int() == 0
