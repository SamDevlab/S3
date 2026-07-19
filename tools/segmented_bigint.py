import typing
from copy import deepcopy

# Base300BigInt: logical base 300 representation
class Base300BigInt:
    __slots__ = ["limbs"]
    BASE = 300

    def __init__(self, limbs: list[int] | None = None):
        if limbs is None:
            self.limbs = [0]
        else:
            self.limbs = limbs
        self.normalize()

    def normalize(self) -> None:
        while len(self.limbs) > 1 and self.limbs[-1] == 0:
            self.limbs.pop()
        if not self.limbs:
            self.limbs = [0]
        # Validates limb bounds
        for limb in self.limbs:
            if not (0 <= limb < self.BASE):
                raise ValueError(f"Limb {limb} out of bounds for base {self.BASE}")

    @classmethod
    def from_int(cls, value: int) -> 'Base300BigInt':
        if value < 0:
            raise ValueError("Negative numbers not supported")
        if value == 0:
            return cls([0])
        limbs = []
        while value > 0:
            limbs.append(value % cls.BASE)
            value //= cls.BASE
        return cls(limbs)

    def to_int(self) -> int:
        value = 0
        multiplier = 1
        for limb in self.limbs:
            value += limb * multiplier
            multiplier *= self.BASE
        return value

    def copy(self) -> 'Base300BigInt':
        return Base300BigInt(list(self.limbs))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Base300BigInt):
            return False
        return self.limbs == other.limbs

    def __lt__(self, other: 'Base300BigInt') -> bool:
        if len(self.limbs) != len(other.limbs):
            return len(self.limbs) < len(other.limbs)
        for i in range(len(self.limbs) - 1, -1, -1):
            if self.limbs[i] != other.limbs[i]:
                return self.limbs[i] < other.limbs[i]
        return False

    def add(self, other: 'Base300BigInt') -> tuple['Base300BigInt', int]:
        max_len = max(len(self.limbs), len(other.limbs))
        out = [0] * max_len
        carry = 0
        carry_count = 0
        for i in range(max_len):
            a = self.limbs[i] if i < len(self.limbs) else 0
            b = other.limbs[i] if i < len(other.limbs) else 0
            s = a + b + carry
            if s >= self.BASE:
                out[i] = s - self.BASE
                carry = 1
                carry_count += 1
            else:
                out[i] = s
                carry = 0
        if carry:
            out.append(carry)
        return Base300BigInt(out), carry_count
        
    def add_small(self, val: int) -> 'Base300BigInt':
        # Add a small integer (must fit in single logical op initially)
        out = list(self.limbs)
        carry = val
        i = 0
        while carry > 0:
            if i < len(out):
                s = out[i] + carry
            else:
                s = carry
                out.append(0)
            
            out[i] = s % self.BASE
            carry = s // self.BASE
            i += 1
        return Base300BigInt(out)

    def sub(self, other: 'Base300BigInt') -> tuple['Base300BigInt', int]:
        if self < other:
            raise ValueError("Result would be negative")
        out = [0] * len(self.limbs)
        borrow = 0
        borrow_count = 0
        for i in range(len(self.limbs)):
            a = self.limbs[i]
            b = other.limbs[i] if i < len(other.limbs) else 0
            diff = a - b - borrow
            if diff < 0:
                out[i] = diff + self.BASE
                borrow = 1
                borrow_count += 1
            else:
                out[i] = diff
                borrow = 0
        return Base300BigInt(out), borrow_count
        
    def sub_small(self, val: int) -> 'Base300BigInt':
        if val == 0:
            return self.copy()
        if self.to_int() < val:
            raise ValueError("Result would be negative")
        out = list(self.limbs)
        borrow = val
        i = 0
        while borrow > 0:
            diff = out[i] - borrow
            if diff < 0:
                # We need to borrow from next limbs, since borrow is essentially int, we do standard subtraction logic
                borrow = 1 + (-diff - 1) // self.BASE
                out[i] = diff + borrow * self.BASE
            else:
                out[i] = diff
                borrow = 0
            i += 1
        return Base300BigInt(out)

    def square(self) -> 'Base300BigInt':
        L = len(self.limbs)
        out = [0] * (2 * L)
        for i in range(L):
            carry = 0
            for j in range(L):
                prod = out[i + j] + self.limbs[i] * self.limbs[j] + carry
                out[i + j] = prod % self.BASE
                carry = prod // self.BASE
            out[i + L] = carry
        return Base300BigInt(out)

    def multiply(self, other: 'Base300BigInt') -> 'Base300BigInt':
        L1 = len(self.limbs)
        L2 = len(other.limbs)
        out = [0] * (L1 + L2)
        for i in range(L1):
            carry = 0
            for j in range(L2):
                prod = out[i + j] + self.limbs[i] * other.limbs[j] + carry
                out[i + j] = prod % self.BASE
                carry = prod // self.BASE
            out[i + L2] = carry
        return Base300BigInt(out)


# BinaryLimbBigInt: physical representation in chunks of 30 bits
class BinaryLimbBigInt:
    __slots__ = ["limbs"]
    BITS = 30
    BASE = 1 << BITS
    MASK = BASE - 1

    def __init__(self, limbs: list[int] | None = None):
        if limbs is None:
            self.limbs = [0]
        else:
            self.limbs = limbs
        self.normalize()

    def normalize(self) -> None:
        while len(self.limbs) > 1 and self.limbs[-1] == 0:
            self.limbs.pop()
        if not self.limbs:
            self.limbs = [0]

    @classmethod
    def from_int(cls, value: int) -> 'BinaryLimbBigInt':
        if value < 0:
            raise ValueError("Negative numbers not supported")
        if value == 0:
            return cls([0])
        limbs = []
        while value > 0:
            limbs.append(value & cls.MASK)
            value >>= cls.BITS
        return cls(limbs)

    def to_int(self) -> int:
        value = 0
        for i, limb in enumerate(self.limbs):
            value += limb << (i * self.BITS)
        return value

    def copy(self) -> 'BinaryLimbBigInt':
        return BinaryLimbBigInt(list(self.limbs))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BinaryLimbBigInt):
            return False
        return self.limbs == other.limbs

    def __lt__(self, other: 'BinaryLimbBigInt') -> bool:
        if len(self.limbs) != len(other.limbs):
            return len(self.limbs) < len(other.limbs)
        for i in range(len(self.limbs) - 1, -1, -1):
            if self.limbs[i] != other.limbs[i]:
                return self.limbs[i] < other.limbs[i]
        return False

    def add(self, other: 'BinaryLimbBigInt') -> tuple['BinaryLimbBigInt', int]:
        max_len = max(len(self.limbs), len(other.limbs))
        out = [0] * max_len
        carry = 0
        carry_count = 0
        for i in range(max_len):
            a = self.limbs[i] if i < len(self.limbs) else 0
            b = other.limbs[i] if i < len(other.limbs) else 0
            s = a + b + carry
            if s >= self.BASE:
                out[i] = s - self.BASE
                carry = 1
                carry_count += 1
            else:
                out[i] = s
                carry = 0
        if carry:
            out.append(carry)
        return BinaryLimbBigInt(out), carry_count

    def sub(self, other: 'BinaryLimbBigInt') -> tuple['BinaryLimbBigInt', int]:
        if self < other:
            raise ValueError("Result would be negative")
        out = [0] * len(self.limbs)
        borrow = 0
        borrow_count = 0
        for i in range(len(self.limbs)):
            a = self.limbs[i]
            b = other.limbs[i] if i < len(other.limbs) else 0
            diff = a - b - borrow
            if diff < 0:
                out[i] = diff + self.BASE
                borrow = 1
                borrow_count += 1
            else:
                out[i] = diff
                borrow = 0
        return BinaryLimbBigInt(out), borrow_count

    def sub_small(self, val: int) -> 'BinaryLimbBigInt':
        if val == 0:
            return self.copy()
        out = list(self.limbs)
        borrow = val
        i = 0
        while borrow > 0:
            if i >= len(out):
                raise ValueError("Result would be negative")
            diff = out[i] - borrow
            if diff < 0:
                borrow = 1 + (-diff - 1) // self.BASE
                out[i] = diff + borrow * self.BASE
            else:
                out[i] = diff
                borrow = 0
            i += 1
        return BinaryLimbBigInt(out)

    def square(self) -> 'BinaryLimbBigInt':
        L = len(self.limbs)
        out = [0] * (2 * L)
        for i in range(L):
            carry = 0
            for j in range(L):
                prod = out[i + j] + self.limbs[i] * self.limbs[j] + carry
                out[i + j] = prod & self.MASK
                carry = prod >> self.BITS
            out[i + L] = carry
        return BinaryLimbBigInt(out)

    def mersenne_reduce(self, p: int) -> 'BinaryLimbBigInt':
        """
        Reduces modulo (2^p - 1).
        Uses the identity 2^p = 1 mod (2^p - 1).
        """
        # Split self into upper and lower parts at bit p
        limb_idx = p // self.BITS
        bit_idx = p % self.BITS

        # To avoid mutation of self, we create a copy for the loop
        current = self
        while True:
            # Check if current value is smaller than or equal to M_p
            # We will just do a folding pass. If the upper part is 0, we can stop,
            # except if it's exactly 2^p - 1 which can be reduced to 0 but standard 
            # implementations often leave it or check at the end. We'll fold until upper is 0.
            if len(current.limbs) <= limb_idx:
                break

            # Extract upper bits
            upper_limbs = []
            lower_limbs = current.limbs[:limb_idx]
            
            if bit_idx == 0:
                upper_limbs = current.limbs[limb_idx:]
            else:
                # Need to shift upper limbs
                mask_lower = (1 << bit_idx) - 1
                # Lower part retains up to limb_idx + 1 (masked)
                lower_limbs.append(current.limbs[limb_idx] & mask_lower)
                
                # Upper part needs shifting
                carry_shift = 0
                for i in range(limb_idx, len(current.limbs)):
                    val = current.limbs[i]
                    # The lowest bits of val (up to bit_idx) are left behind, we want the rest
                    shifted_val = val >> bit_idx
                    if i + 1 < len(current.limbs):
                        next_val = current.limbs[i + 1]
                        # bring bottom bits of next_val to top
                        bits_to_pull = next_val & ((1 << bit_idx) - 1)
                        shifted_val |= bits_to_pull << (self.BITS - bit_idx)
                    upper_limbs.append(shifted_val)
                    
            upper = BinaryLimbBigInt(upper_limbs)
            lower = BinaryLimbBigInt(lower_limbs)
            
            if len(upper.limbs) == 1 and upper.limbs[0] == 0:
                current = lower
                break
                
            current, _ = lower.add(upper)

        # After folding, current could still be exactly 2^p - 1. 
        # But for Lucas-Lehmer it's typically fine, we can do a final subtract if needed.
        # Let's check if it's exactly 2^p - 1
        
        # 2^p - 1 representation
        mp_limbs = [(1 << self.BITS) - 1] * limb_idx
        if bit_idx > 0:
            mp_limbs.append((1 << bit_idx) - 1)
        mp = BinaryLimbBigInt(mp_limbs)
        
        if current == mp:
            return BinaryLimbBigInt([0])
        elif mp < current:
            current, _ = current.sub(mp)
            
        return current


def square_segment(limbs: list[int], start_i: int, end_i: int, full_limbs: list[int], mask: int, bits: int) -> list[int]:
    """
    Computes partial products for indices i in [start_i, end_i).
    Returns an array of length len(full_limbs) + end_i to hold the partial products.
    """
    L = len(full_limbs)
    out = [0] * (L + end_i)
    for i in range(start_i, end_i):
        carry = 0
        limb_i = limbs[i - start_i]
        for j in range(L):
            prod = out[i + j] + limb_i * full_limbs[j] + carry
            out[i + j] = prod & mask
            carry = prod >> bits
        out[i + L] = carry
    return out


def combine_segments(segments: list[list[int]], mask: int, bits: int) -> list[int]:
    """
    Combines partial products and resolves carries.
    """
    if not segments:
        return [0]
    
    max_len = max(len(s) for s in segments)
    out = [0] * max_len
    
    for seg in segments:
        for i in range(len(seg)):
            out[i] += seg[i]
            
    # Resolve carries
    carry = 0
    for i in range(max_len):
        s = out[i] + carry
        out[i] = s & mask
        carry = s >> bits
        
    while carry > 0:
        out.append(carry & mask)
        carry >>= bits
        
    return out
