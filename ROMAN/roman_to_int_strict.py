#!/usr/bin/env ipython

import re  # for regex


def roman_to_int_strict(s: str) -> int:
    """
    Converts a Roman numeral string to an integer, strictly enforcing
    validity rules (no more than three repeats, no repetition of V, L, D,
    valid subtractive pairs).
    """
    # Handle Empty String
    if not s:
        return 0

    roman_map = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

    # Strict Input Validation using Regex
    # This pattern captures the rules:
    # - M, C, X, I can repeat up to three times (e.g., MMM, CCC, III)
    # - V, L, D cannot repeat (e.g., VV is invalid)
    # - Valid subtractive pairs: IV, IX, XL, XC, CD, CM

    # Pattern explanation:
    # ^(M{0,3})          -> Hundreds/Thousands: 0 to 3 'M's
    # (CM|CD|D?C{0,3})   -> Hundreds: CM/CD, or D followed by up to 3 C's, or up to 3 C's
    # (XL|XC|L?X{0,3})   -> Tens: XL/XC, or L followed by up to 3 X's, or up to 3 X's
    # (IV|IX|V?I{0,3})$  -> Ones: IV/IX, or V followed by up to 3 I's, or up to 3 I's
    roman_pattern = re.compile(
        r"^(M{0,3})(CM|CD|D?C{0,3})(XL|XC|L?X{0,3})(IV|IX|V?I{0,3})$"
    )

    if not roman_pattern.fullmatch(s):
        # This catches "A", "VV", "IIII", "IC", and other structurally invalid numerals.
        raise ValueError(
            f"'{s}' is not a valid Roman numeral string (e.g., invalid characters, repetition, or sequence)."
        )

    # Conversion Logic (The original correct iterative algorithm)
    converted_number = 0

    for i in range(len(s)):
        # We can now safely access the map, as the regex already checked for invalid characters.
        current_number = roman_map[s[i]]

        # Look ahead for the next number, 0 if at the end of the string
        next_number = roman_map[s[i + 1]] if i + 1 < len(s) else 0

        # Subtractive rule logic: if current is less than next, subtract it.
        if current_number < next_number:
            converted_number -= current_number
        else:
            converted_number += current_number

    return converted_number


# --- Test Cases --- (RUN to test functionality without pytest)
# Invalid Cases:
# try:
#     print(f"'A' -> {roman_to_int_strict('A')}")
# except ValueError as e:
#     print(f"Error for 'A': {e}")

# try:
#     print(f"'VV' -> {roman_to_int_strict('VV')}")
# except ValueError as e:
#     print(f"Error for 'VV': {e}")

# try:
#     print(f"'IIII' -> {roman_to_int_strict('IIII')}")
# except ValueError as e:
#     print(f"Error for 'IIII': {e}")

# try:
#     print(f"'IC' -> {roman_to_int_strict('IC')}")
# except ValueError as e:
#     print(f"Error for 'IC': {e}")

# print("-" * 20)

# Valid Cases:
# print(f"'III' -> {roman_to_int_strict('III')}")  # 3
# print(f"'IV' -> {roman_to_int_strict('IV')}")  # 4
# print(f"'MCMXCIV' -> {roman_to_int_strict('MCMXCIV')}")  # 1994
