#!/usr/bin/env ipython

import pytest

# Assuming your function is saved in a file named roman_converter.py
from roman_to_int_strict import roman_to_int_strict


# Test Valid Conversions
@pytest.mark.parametrize(
    "roman, integer",
    [
        # Basic Additive
        ("I", 1),
        ("III", 3),
        ("V", 5),
        ("X", 10),
        ("L", 50),
        ("D", 500),
        ("M", 1000),
        ("XII", 12),
        ("LVII", 57),
        # Basic Subtractive
        ("IV", 4),
        ("IX", 9),
        ("XL", 40),
        ("XC", 90),
        ("CD", 400),
        ("CM", 900),
        # Compound Numbers
        ("MCMXCIV", 1994),  # 1000 + 900 + 90 + 4
        ("MMXXV", 2025),
        ("MMMDCCCLXXXVIII", 3888),  # Largest valid number
    ],
)
def test_valid_conversions(roman, integer):
    """Tests standard valid Roman numeral inputs."""
    assert roman_to_int_strict(roman) == integer


# Test Edge Cases
def test_empty_string():
    """Tests the required edge case of an empty string."""
    assert roman_to_int_strict("") == 0


# Test Invalid Input Cases
@pytest.mark.parametrize(
    "invalid_roman",
    [
        # Invalid Characters (violates regex check)
        "A",
        "roman",
        "123",
        # Invalid Repetition of V, L, D (violates regex check)
        "VV",
        "LL",
        "DD",
        # Too many repeats (violates regex check)
        "IIII",
        "XXXX",
        "CCCC",
        "MMMM",
        # Invalid Subtraction Pairs (violates regex check)
        "IC",
        "ID",
        "IM",
        "VX",  # V, L, D cannot be subtracted
        "IL",
        # Combination of invalid characters and valid ones
        "XIIA",
    ],
)
def test_invalid_input_raises_error(invalid_roman):
    """Tests various invalid inputs that should raise a ValueError."""
    with pytest.raises(ValueError) as excinfo:
        roman_to_int_strict(invalid_roman)

    # check if the error message is descriptive
    assert "not a valid Roman numeral string" in str(excinfo.value)
