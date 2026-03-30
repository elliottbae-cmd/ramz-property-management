"""Deterministic serial number → manufacture date decoders for common
commercial restaurant equipment manufacturers.

Each decoder returns a SerialDecodeResult with:
  - decoded (bool): True if the format was recognized and date extracted
  - manufacture_date (date | None): the decoded date
  - confidence ('verified' | 'likely' | 'unverified'): how reliable the format is
  - method (str): human-readable description of the decode logic
  - notes (str): any caveats

Confidence levels:
  'verified'   — format confirmed against a known sample (serial → date cross-checked)
  'likely'     — format is documented but not cross-checked against this serial
  'unverified' — format unknown for this manufacturer; not decoded

HOW TO ADD A NEW MANUFACTURER
------------------------------
1. Write a function  _decode_<brand>(serial: str) -> SerialDecodeResult
2. Register it in DECODERS dict below (lower-case, strip spaces/hyphens)
3. Add a note on the source / sample used to verify it.

If you don't have a confirmed format, do NOT add a guess — return _unknown().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class SerialDecodeResult:
    decoded: bool
    manufacture_date: Optional[date] = None
    confidence: str = "unverified"   # 'verified' | 'likely' | 'unverified'
    method: str = ""
    notes: str = ""


def _unknown(manufacturer: str = "") -> SerialDecodeResult:
    return SerialDecodeResult(
        decoded=False,
        confidence="unverified",
        method="No documented format on file",
        notes=(
            f"Serial number format for '{manufacturer}' is not yet in our decoder library. "
            "PSP should contact the manufacturer directly to obtain the manufacture date."
        ),
    )


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def decode_manufacture_date(manufacturer: str, serial: str) -> SerialDecodeResult:
    """Attempt to decode the manufacture date from a serial number.

    Parameters
    ----------
    manufacturer : str   e.g. "Hoshizaki", "Manitowoc Ice"
    serial       : str   e.g. "N30466K"

    Returns
    -------
    SerialDecodeResult — always returns a result; decoded=False if unknown.
    """
    if not manufacturer or not serial:
        return _unknown()

    # Normalise key: lower-case, strip spaces / hyphens / punctuation
    key = re.sub(r"[\s\-_./]", "", manufacturer.lower())

    # Try progressively shorter prefixes so "hoshizaki america" matches "hoshizaki"
    for decoder_key, decoder_fn in DECODERS.items():
        if key.startswith(decoder_key) or decoder_key.startswith(key):
            return decoder_fn(serial.strip())

    return _unknown(manufacturer)


# ------------------------------------------------------------------
# Hoshizaki
# ------------------------------------------------------------------
# Format source: Parts Town documentation (verified against serial N30466K
# which Hoshizaki confirmed as manufactured October 2023).
#
# Serial format: [year_letter][sequential_digits][month_letter]
#
# Year letter encodes the LAST DIGIT of the manufacture year.
# Letters cycle through the alphabet skipping I, mapping to digits 1-9, 0:
#   A→1, B→2, C→3, D→4, E→5, F→6, G→7, H→8,  (I skipped)
#   J→9, K→0, L→1, M→2, N→3, O→4, P→5, Q→6, R→7, S→8, T→9, U→0 ...
# The decade is inferred from context (most active equipment is 2020s).
#
# Month letter (same skip-I alphabet, A=Jan … M=Dec):
#   A=Jan(1), B=Feb(2), C=Mar(3), D=Apr(4), E=May(5), F=Jun(6),
#   G=Jul(7), H=Aug(8),  (I skipped)
#   J=Sep(9), K=Oct(10), L=Nov(11), M=Dec(12)
#
# Verified example: N30466K
#   N → last digit 3 → 2023
#   30466 → sequential production number
#   K → October
#   ⟹ Manufactured October 2023  ✅
#
# Warranty (F-1002MRJZ-C and similar Hoshizaki ice machines):
#   3-year Parts & Labor on entire machine
#   5-year Parts on compressor and air-cooled condenser coil
#   Validate at: secure.hoshizakiamerica.com/warrantyvalidation
# ------------------------------------------------------------------

# Year letter → last digit of year (alphabet skipping I)
_HOSHIZAKI_YEAR_LETTERS = {
    c: (i % 10) for i, c in enumerate(
        [ch for ch in "ABCDEFGHJKLMNOPQRSTUVWXYZ"], start=1
    )
}

# Month letter → month number (alphabet skipping I, A=1 … M=12)
_HOSHIZAKI_MONTH_LETTERS = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6,
    "G": 7, "H": 8, "J": 9, "K": 10, "L": 11, "M": 12,
}


def _decode_hoshizaki(serial: str) -> SerialDecodeResult:
    """Decode a Hoshizaki serial number to manufacture date.

    Format: [year_letter][sequential_number][month_letter]
    Example: N30466K → 2023-10 (October 2023)
    """
    s = serial.upper().strip()

    # Pattern: [1 letter][digits][1 letter]
    m = re.match(r"^([A-Z])(\d+)([A-Z])$", s)
    if not m:
        return SerialDecodeResult(
            decoded=False,
            confidence="unverified",
            method="Serial does not match Hoshizaki [year_letter][digits][month_letter] pattern",
            notes=(
                f"Serial '{serial}' does not match the documented format. "
                "Expected: one letter, then digits, then one letter (e.g. N30466K). "
                "PSP should contact Hoshizaki America (1-800-438-6087 or "
                "hoshizakiamerica.com) to confirm the manufacture date. "
                "Warranty can also be validated by serial at "
                "secure.hoshizakiamerica.com/warrantyvalidation"
            ),
        )

    year_char = m.group(1)
    month_char = m.group(3)

    year_digit = _HOSHIZAKI_YEAR_LETTERS.get(year_char)
    month = _HOSHIZAKI_MONTH_LETTERS.get(month_char)

    if year_digit is None or month is None:
        return SerialDecodeResult(
            decoded=False,
            confidence="unverified",
            method=f"Unrecognised year code '{year_char}' or month code '{month_char}'",
            notes=(
                "PSP should contact Hoshizaki America (1-800-438-6087) "
                "or validate warranty at secure.hoshizakiamerica.com/warrantyvalidation"
            ),
        )

    # Infer the most plausible 4-digit year.
    # Equipment in active service is almost always manufactured within the last 10 years.
    today_year = date.today().year
    candidates = [
        y for y in range(today_year - 10, today_year + 2)
        if y % 10 == year_digit
    ]
    if not candidates:
        return _unknown("Hoshizaki")

    # Pick the most recent candidate that isn't in the future
    year_4d = max(y for y in candidates if y <= today_year + 1)

    try:
        mfg_date = date(year_4d, month, 1)
    except ValueError:
        return _unknown("Hoshizaki")

    return SerialDecodeResult(
        decoded=True,
        manufacture_date=mfg_date,
        confidence="verified",
        method=(
            f"Hoshizaki [year_letter][seq][month_letter] format: "
            f"'{year_char}'→year ending {year_digit}→{year_4d}, "
            f"'{month_char}'→month {month:02d}"
        ),
        notes=(
            "Format verified against serial N30466K (confirmed October 2023 by manufacturer). "
            "Source: Parts Town serial number documentation. "
            "Validate warranty at: secure.hoshizakiamerica.com/warrantyvalidation"
        ),
    )


# ------------------------------------------------------------------
# Manitowoc Ice
# ------------------------------------------------------------------
# Format source: Manitowoc Foodservice documentation
# Serial format: [2-letter plant][2-digit year][2-digit week][sequence]
# e.g. AD2310xxxx → plant=AD, year=23 (2023), week=10
#
# ------------------------------------------------------------------

def _decode_manitowoc(serial: str) -> SerialDecodeResult:
    """Decode a Manitowoc ice machine serial number."""
    s = serial.upper().strip()

    # Pattern: [2 letters][2-digit year][2-digit week][remaining]
    m = re.match(r"^([A-Z]{2})(\d{2})(\d{2})\w+", s)
    if m:
        plant = m.group(1)
        year_2d = int(m.group(2))
        week = int(m.group(3))

        if 1 <= week <= 53:
            year_4d = 2000 + year_2d
            if 2000 <= year_4d <= date.today().year + 1:
                try:
                    # Convert week number to approximate date (use Jan 1 + weeks)
                    import datetime as _dt
                    # ISO week date: year, week, day=1 (Monday)
                    mfg_date = _dt.date.fromisocalendar(year_4d, week, 1)
                    return SerialDecodeResult(
                        decoded=True,
                        manufacture_date=mfg_date,
                        confidence="likely",
                        method=(
                            f"Manitowoc [plant][YY][WW][seq] format: "
                            f"plant='{plant}', year='{m.group(2)}'→{year_4d}, "
                            f"week='{m.group(3)}'→week {week}"
                        ),
                        notes=(
                            "Manitowoc format: [2-letter plant][YY][WW][sequence]. "
                            "Date is start of that ISO week. "
                            "Verify with Manitowoc (1-888-MANITOWOC) if warranty decision is critical."
                        ),
                    )
                except (ValueError, AttributeError):
                    pass

    return SerialDecodeResult(
        decoded=False,
        confidence="unverified",
        method="Serial does not match known Manitowoc [plant][YY][WW] pattern",
        notes=(
            f"Serial '{serial}' does not match the documented Manitowoc format. "
            "PSP should contact Manitowoc Foodservice to confirm the manufacture date."
        ),
    )


# ------------------------------------------------------------------
# True Manufacturing (refrigeration)
# ------------------------------------------------------------------
# Format source: True Manufacturing service docs
# Serial format: [7-digit sequence]-[2-digit year][2-digit month]
# e.g. 1234567-2310 → year=23(2023), month=10
# Also seen: [letter][6 digits][YYMM] without hyphen
# ------------------------------------------------------------------

def _decode_true(serial: str) -> SerialDecodeResult:
    """Decode a True Manufacturing refrigerator/freezer serial number."""
    s = serial.upper().strip()

    # Pattern with hyphen: XXXXXXX-YYMM
    m = re.match(r"^\d{6,8}-(\d{2})(\d{2})$", s)
    if m:
        year_2d = int(m.group(1))
        month = int(m.group(2))
        if 1 <= month <= 12:
            year_4d = 2000 + year_2d
            if 2000 <= year_4d <= date.today().year + 1:
                try:
                    mfg_date = date(year_4d, month, 1)
                    return SerialDecodeResult(
                        decoded=True,
                        manufacture_date=mfg_date,
                        confidence="likely",
                        method=(
                            f"True Manufacturing [seq]-[YYMM] format: "
                            f"year='{m.group(1)}'→{year_4d}, month='{m.group(2)}'→{month:02d}"
                        ),
                        notes=(
                            "True Manufacturing format: [sequence]-[YYMM]. "
                            "Verify with True (1-800-TRUE-MFG) if warranty decision is critical."
                        ),
                    )
                except ValueError:
                    pass

    return SerialDecodeResult(
        decoded=False,
        confidence="unverified",
        method="Serial does not match known True Manufacturing [seq]-[YYMM] pattern",
        notes=(
            f"Serial '{serial}' does not match the documented True Manufacturing format. "
            "PSP should contact True Manufacturing to confirm the manufacture date."
        ),
    )


# ------------------------------------------------------------------
# Beverage-Air
# ------------------------------------------------------------------
# Format source: Beverage-Air service documentation
# Serial format: [2-digit year][2-digit month][sequence letters/digits]
# e.g. 2310xxxxx → year=23(2023), month=10
# ------------------------------------------------------------------

def _decode_beverageair(serial: str) -> SerialDecodeResult:
    """Decode a Beverage-Air serial number."""
    s = serial.upper().strip()

    m = re.match(r"^(\d{2})(\d{2})\w+", s)
    if m:
        year_2d = int(m.group(1))
        month = int(m.group(2))
        if 1 <= month <= 12:
            year_4d = 2000 + year_2d
            if 2000 <= year_4d <= date.today().year + 1:
                try:
                    mfg_date = date(year_4d, month, 1)
                    return SerialDecodeResult(
                        decoded=True,
                        manufacture_date=mfg_date,
                        confidence="likely",
                        method=(
                            f"Beverage-Air [YYMM][seq] format: "
                            f"year='{m.group(1)}'→{year_4d}, month='{m.group(2)}'→{month:02d}"
                        ),
                        notes=(
                            "Beverage-Air format: [YY][MM][sequence]. "
                            "Verify with Beverage-Air (1-800-845-9800) if warranty decision is critical."
                        ),
                    )
                except ValueError:
                    pass

    return SerialDecodeResult(
        decoded=False,
        confidence="unverified",
        method="Serial does not match known Beverage-Air [YYMM][seq] pattern",
        notes=(
            f"Serial '{serial}' does not match the documented Beverage-Air format. "
            "PSP should contact Beverage-Air to confirm the manufacture date."
        ),
    )


# ------------------------------------------------------------------
# Henny Penny (fryers, holding cabinets)
# ------------------------------------------------------------------
# Format source: Henny Penny service documentation
# Serial format: [letter=year][letter=month][sequence]
# Year codes (A=2001, B=2002, ... rolling):
#   A=2001/2027, B=2002/2028, C=2003, D=2004, E=2005, F=2006,
#   G=2007, H=2008, J=2009(I skipped), K=2010, L=2011, M=2012,
#   N=2013, P=2014(O skipped), R=2015(Q skipped), S=2016, T=2017,
#   U=2018, V=2019, W=2020, X=2021, Y=2022, Z=2023,
#   then cycles: A=2024 or 2001 depending on context
# Month codes (A=Jan, B=Feb, C=Mar, D=Apr, E=May, F=Jun,
#              G=Jul, H=Aug, J=Sep(I skipped), K=Oct, L=Nov, M=Dec)
# ------------------------------------------------------------------

_HP_YEAR = {
    "A": [2001, 2024], "B": [2002, 2025], "C": [2003, 2026],
    "D": [2004], "E": [2005], "F": [2006], "G": [2007], "H": [2008],
    "J": [2009], "K": [2010], "L": [2011], "M": [2012], "N": [2013],
    "P": [2014], "R": [2015], "S": [2016], "T": [2017], "U": [2018],
    "V": [2019], "W": [2020], "X": [2021], "Y": [2022], "Z": [2023],
}
_HP_MONTH = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6,
    "G": 7, "H": 8, "J": 9, "K": 10, "L": 11, "M": 12,
}


def _decode_hennypenny(serial: str) -> SerialDecodeResult:
    """Decode a Henny Penny serial number."""
    s = serial.upper().strip()

    if len(s) < 3:
        return _unknown("Henny Penny")

    year_char = s[0]
    month_char = s[1]

    year_options = _HP_YEAR.get(year_char)
    month = _HP_MONTH.get(month_char)

    if year_options and month:
        # Pick the most recent plausible year
        today = date.today()
        best_year = max(
            (y for y in year_options if y <= today.year + 1),
            default=None,
        )
        if best_year:
            try:
                mfg_date = date(best_year, month, 1)
                return SerialDecodeResult(
                    decoded=True,
                    manufacture_date=mfg_date,
                    confidence="likely",
                    method=(
                        f"Henny Penny letter-date format: "
                        f"year_char='{year_char}'→{best_year}, "
                        f"month_char='{month_char}'→{month:02d}"
                    ),
                    notes=(
                        "Henny Penny format: [year letter][month letter][sequence]. "
                        "Year letters cycle — if equipment is older/newer than expected, "
                        f"alternate year candidates: {year_options}. "
                        "Verify with Henny Penny (1-800-417-8417) if critical."
                    ),
                )
            except ValueError:
                pass

    return SerialDecodeResult(
        decoded=False,
        confidence="unverified",
        method="Serial does not match known Henny Penny letter-date pattern",
        notes=(
            f"Serial '{serial}' does not match the documented Henny Penny format. "
            "PSP should contact Henny Penny to confirm the manufacture date."
        ),
    )


# ------------------------------------------------------------------
# Scotsman Ice Systems
# ------------------------------------------------------------------
# Format: [plant letter][2-digit year][2-digit month][sequence]
# e.g. C2310XXXXX → plant=C, year=23(2023), month=10
# ------------------------------------------------------------------

def _decode_scotsman(serial: str) -> SerialDecodeResult:
    s = serial.upper().strip()
    m = re.match(r"^([A-Z])(\d{2})(\d{2})\w+", s)
    if m:
        year_2d = int(m.group(2))
        month = int(m.group(3))
        if 1 <= month <= 12:
            year_4d = 2000 + year_2d
            if 2000 <= year_4d <= date.today().year + 1:
                try:
                    mfg_date = date(year_4d, month, 1)
                    return SerialDecodeResult(
                        decoded=True,
                        manufacture_date=mfg_date,
                        confidence="likely",
                        method=(
                            f"Scotsman [plant][YY][MM][seq] format: "
                            f"plant='{m.group(1)}', year→{year_4d}, month→{month:02d}"
                        ),
                        notes=(
                            "Scotsman format: [plant letter][YY][MM][sequence]. "
                            "Verify with Scotsman Ice (1-800-726-8762) if warranty decision is critical."
                        ),
                    )
                except ValueError:
                    pass

    return SerialDecodeResult(
        decoded=False,
        confidence="unverified",
        method="Serial does not match known Scotsman [plant][YY][MM] pattern",
        notes=f"PSP should contact Scotsman Ice to confirm manufacture date for serial '{serial}'.",
    )


# ------------------------------------------------------------------
# Decoder registry — add new manufacturers here
# key: lower-case, no spaces/hyphens (matched via startswith)
# ------------------------------------------------------------------

DECODERS: dict[str, callable] = {
    "hoshizaki":    _decode_hoshizaki,
    "manitowoc":    _decode_manitowoc,
    "true":         _decode_true,
    "beverageair":  _decode_beverageair,
    "beverageaire": _decode_beverageair,  # common misspelling
    "hennypenny":   _decode_hennypenny,
    "scotsman":     _decode_scotsman,
}


# ------------------------------------------------------------------
# Utility: summarise result for display
# ------------------------------------------------------------------

def format_decode_result(result: SerialDecodeResult) -> str:
    """Return a one-line human-readable summary of the decode result."""
    if not result.decoded or not result.manufacture_date:
        return f"Unknown — {result.notes}"
    d = result.manufacture_date
    conf_label = {"verified": "✅ Verified", "likely": "🔍 Likely", "unverified": "❓ Unverified"}.get(
        result.confidence, result.confidence
    )
    return f"{d.strftime('%B %Y')} ({conf_label}) — {result.method}"
