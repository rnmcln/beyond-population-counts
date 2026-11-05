"""Read the revised GENESIS Flat-File CSV format without losing metadata."""

from __future__ import annotations

import re
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

from neurodemography.age_groups import diagnosis_age_group
from neurodemography.codebook import normalize_icd3

GERMAN_COLUMNS = {
    "Statistik_Code": "statistics_code",
    "Statistik_Label": "statistics_label",
    "Zeit_Code": "time_code",
    "Zeit_Label": "time_label",
    "Zeit": "time",
}
MISSING_SIGNS = {"", "-", ".", "...", "/", "x"}


def _canonical_column(column: str) -> str:
    column = column.removeprefix("\ufeff")
    if column in GERMAN_COLUMNS:
        return GERMAN_COLUMNS[column]
    replacements = (
        (r"^(\d+)_Merkmal_Code$", r"\1_variable_code"),
        (r"^(\d+)_Merkmal_Label$", r"\1_variable_label"),
        (r"^(\d+)_Auspraegung_Code$", r"\1_variable_attribute_code"),
        (r"^(\d+)_Auspraegung_Label$", r"\1_variable_attribute_label"),
    )
    for pattern, replacement in replacements:
        if re.match(pattern, column):
            return re.sub(pattern, replacement, column)
    return column


def _csv_member(path: Path) -> tuple[zipfile.ZipFile, str] | None:
    if not zipfile.is_zipfile(path):
        return None
    archive = zipfile.ZipFile(path)
    members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if len(members) != 1:
        archive.close()
        raise ValueError(f"Expected one CSV in GENESIS archive, found {len(members)}: {members}")
    return archive, members[0]


def read_ffcsv(path: str | Path) -> pd.DataFrame:
    """Read a GENESIS CSV or its single-file ZIP archive as lossless strings."""

    source = Path(path)
    archived = _csv_member(source)
    if archived is None:
        frame = pd.read_csv(
            source,
            sep=";",
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
        )
    else:
        archive, member = archived
        try:
            with archive.open(member) as handle:
                frame = pd.read_csv(
                    handle,
                    sep=";",
                    dtype=str,
                    keep_default_na=False,
                    encoding="utf-8-sig",
                )
        finally:
            archive.close()
    frame.columns = [_canonical_column(str(column)) for column in frame.columns]
    required = {"statistics_code", "statistics_label", "time"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Not a revised GENESIS flat-file CSV; missing {sorted(missing)}")
    return frame


def dimension_map(frame: pd.DataFrame) -> dict[str, tuple[str, str]]:
    """Map each dimension label to its attribute-code and attribute-label columns."""

    dimensions: dict[str, tuple[str, str]] = {}
    for index in range(1, 100):
        variable_label = f"{index}_variable_label"
        attribute_code = f"{index}_variable_attribute_code"
        attribute_label = f"{index}_variable_attribute_label"
        present = {variable_label, attribute_code, attribute_label}.intersection(frame.columns)
        if not present:
            break
        required = {variable_label, attribute_code, attribute_label}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"GENESIS dimension {index} is incomplete: {sorted(missing)}")
        labels = frame[variable_label].str.strip().drop_duplicates().tolist()
        if len(labels) != 1 or not labels[0]:
            raise ValueError(f"GENESIS dimension {index} has unstable label values: {labels}")
        dimensions[labels[0]] = (attribute_code, attribute_label)
    return dimensions


def value_columns(frame: pd.DataFrame) -> list[str]:
    """Return statistical value columns, excluding metadata and quality columns."""

    if {"value", "value_variable_code", "value_variable_label"}.issubset(frame.columns):
        return ["value"]
    metadata = {
        "statistics_code",
        "statistics_label",
        "time_code",
        "time_label",
        "time",
    }
    metadata.update(column for column in frame.columns if "_variable_" in column)
    return [
        column
        for column in frame.columns
        if column not in metadata and not column.lower().endswith("__q")
    ]


def _years(series: pd.Series) -> pd.Series:
    extracted = series.astype("string").str.extract(r"(?<!\d)(\d{4})(?!\d)", expand=False)
    if extracted.isna().any():
        examples = series.loc[extracted.isna()].head().tolist()
        raise ValueError(f"Unrecognised GENESIS time values: {examples}")
    return extracted.astype(int)


def parse_value(
    series: pd.Series,
    *,
    decimal: str = ",",
    dash_is_zero: bool = False,
) -> pd.Series:
    """Convert GENESIS values while retaining non-numeric quality signs as NA.

    GENESIS defines ``-`` as "nothing present". It is converted to zero only for
    tables where an explicit zero is analytically meaningful and the caller opts in.
    """

    text = series.astype("string").str.strip()
    missing = text.isin(MISSING_SIGNS)
    if dash_is_zero:
        dash = text.eq("-")
        text = text.mask(dash, "0")
        missing = missing & ~dash
    if decimal == ",":
        text = text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    elif decimal != ".":
        raise ValueError("Decimal separator must be ',' or '.'")
    return pd.to_numeric(text.mask(missing), errors="raise")


def _dimension(
    frame: pd.DataFrame,
    *label_fragments: str,
) -> tuple[str, str]:
    matches: list[tuple[str, str]] = []
    for index in range(1, 100):
        variable_label = f"{index}_variable_label"
        attribute_code = f"{index}_variable_attribute_code"
        attribute_label = f"{index}_variable_attribute_label"
        if variable_label not in frame:
            break
        labels = frame[variable_label].astype("string").str.strip().drop_duplicates()
        if any(
            fragment.casefold() in label.casefold()
            for label in labels
            for fragment in label_fragments
        ):
            missing = {attribute_code, attribute_label}.difference(frame.columns)
            if missing:
                raise ValueError(f"GENESIS dimension {index} is incomplete: {sorted(missing)}")
            matches.append((attribute_code, attribute_label))
    if len(matches) != 1:
        raise ValueError(
            f"Expected one GENESIS dimension matching {label_fragments}, found {len(matches)}"
        )
    return matches[0]


def _select_value(
    frame: pd.DataFrame,
    fragments: tuple[str, ...],
    explicit: str | None,
) -> tuple[pd.DataFrame, str]:
    def searchable(value: object) -> str:
        normalized = unicodedata.normalize("NFKD", str(value).casefold())
        ascii_text = "".join(
            character for character in normalized if not unicodedata.combining(character)
        )
        return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()

    searchable_fragments = [searchable(fragment) for fragment in fragments]
    long_columns = {"value", "value_variable_code", "value_variable_label"}
    if long_columns.issubset(frame.columns):
        identities = frame[["value_variable_code", "value_variable_label"]].drop_duplicates()
        if explicit:
            matches = identities.loc[
                identities["value_variable_code"].eq(explicit)
                | identities["value_variable_label"].eq(explicit)
            ]
        else:
            matches = identities.loc[
                identities.apply(
                    lambda row: any(
                        fragment
                        in searchable(f"{row['value_variable_code']} {row['value_variable_label']}")
                        for fragment in searchable_fragments
                    ),
                    axis=1,
                )
            ]
        if len(matches) != 1:
            available = identities.to_dict(orient="records")
            raise ValueError(
                f"Expected one long-form value variable matching {fragments}, found "
                f"{matches.to_dict(orient='records')}; available: {available}"
            )
        identity = matches.iloc[0]
        selected = frame.loc[
            frame["value_variable_code"].eq(identity["value_variable_code"])
            & frame["value_variable_label"].eq(identity["value_variable_label"])
        ].copy()
        return selected, "value"

    available = value_columns(frame)
    if explicit:
        if explicit not in available:
            raise ValueError(f"Unknown value column {explicit!r}; available: {available}")
        return frame, explicit
    matches = [
        column
        for column in available
        if any(fragment in searchable(column) for fragment in searchable_fragments)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one value column matching {fragments}, found {matches}; "
            "pass the value column explicitly"
        )
    return frame, matches[0]


def _sex(value: object) -> str | None:
    text = str(value).strip().casefold()
    if text in {"männlich", "maennlich", "male"}:
        return "male"
    if text in {"weiblich", "female"}:
        return "female"
    if text in {"insgesamt", "total", "all"}:
        return None
    raise ValueError(f"Unrecognised GENESIS sex category: {value!r}")


def _diagnosis_age_group(value: object, *, topcode: int) -> str | None:
    text = re.sub(r"\s+", " ", str(value).strip().casefold())
    if text in {"insgesamt", "total", "all ages", "alle altersgruppen"}:
        return None
    if re.search(r"^(?:unter|under)\s+1(?!\d)", text):
        return "0"
    lower_match = re.search(r"(\d+)\s*(?:jahre?|years?).*(?:mehr|older|over)", text)
    if lower_match:
        lower = int(lower_match.group(1))
        return f"{topcode}+" if lower >= topcode else f"{lower}+"
    range_match = re.search(r"(\d+)\s*(?:bis\s*unter|to\s*under|[-–—])\s*(\d+)", text)
    if not range_match:
        range_match = re.search(r"(\d+)\s*bis\s*(\d+)", text)
    if range_match:
        lower, upper = map(int, range_match.groups())
        if "bis unter" in text or "to under" in text:
            upper -= 1
        if lower >= topcode:
            return f"{topcode}+"
        if upper >= topcode:
            raise ValueError(f"Age group {value!r} crosses the {topcode}+ top-code boundary")
        return f"{lower}-{upper}"
    raise ValueError(f"Unrecognised GENESIS diagnosis age group: {value!r}")


def _combine_quality(values: pd.Series) -> str:
    observed = sorted({str(value).strip() for value in values if str(value).strip()})
    return ";".join(observed)


def normalize_diagnoses_ffcsv(
    frame: pd.DataFrame,
    *,
    source_table: str = "23131-0002",
    geography: str = "Germany",
    value_column: str | None = None,
    topcode: int = 85,
) -> pd.DataFrame:
    """Normalize national diagnosis flat-file rows to the analysis contract."""

    _, sex_label = _dimension(frame, "Geschlecht", "sex")
    _, age_label = _dimension(frame, "Altersgruppen", "age group")
    diagnosis_code, _ = _dimension(frame, "Hauptdiagnose", "principal diagnosis")
    frame, selected_value = _select_value(
        frame,
        ("Entlassene_Patienten", "discharged_patients"),
        value_column,
    )
    quality_candidates = [
        f"{selected_value.rpartition('__')[0]}__q",
        f"{selected_value}__q",
    ]
    quality_column = next((column for column in quality_candidates if column in frame), None)
    rows = pd.DataFrame(
        {
            "year": _years(frame["time"]),
            "geography": geography,
            "sex": frame[sex_label].map(_sex),
            "age_group": frame[age_label].map(
                lambda value: _diagnosis_age_group(value, topcode=topcode)
            ),
            "icd10": frame[diagnosis_code].map(normalize_icd3),
            "cases": parse_value(frame[selected_value], dash_is_zero=True),
            "quality_flag": (
                frame[quality_column].astype(str).str.strip() if quality_column is not None else ""
            ),
            "source_table": source_table,
        }
    )
    rows = rows.loc[rows["sex"].notna() & rows["age_group"].notna() & rows["icd10"].notna()].copy()
    missing_value = frame.loc[rows.index, selected_value].astype(str).str.strip()
    rows.loc[missing_value.eq("-") & rows["quality_flag"].eq(""), "quality_flag"] = "-"
    rows.loc[rows["cases"].isna() & rows["quality_flag"].eq(""), "quality_flag"] = missing_value
    keys = ["year", "geography", "sex", "age_group", "icd10", "source_table"]

    def complete_sum(values: pd.Series) -> float:
        return float(values.sum()) if values.notna().all() else float("nan")

    return (
        rows.groupby(keys, as_index=False, observed=True, dropna=False)
        .agg(cases=("cases", complete_sum), quality_flag=("quality_flag", _combine_quality))
        .sort_values(keys)
        .reset_index(drop=True)
    )


def _single_age(value: object) -> int | None:
    text = re.sub(r"\s+", " ", str(value).strip().casefold())
    if text in {"insgesamt", "total", "all ages", "alle altersjahre"}:
        return None
    if "unter 1" in text or "under 1" in text:
        return 0
    match = re.search(r"(?<!\d)(\d{1,3})(?!\d)", text)
    if match:
        return int(match.group(1))
    raise ValueError(f"Unrecognised GENESIS single-age category: {value!r}")


def _scenario(value: object) -> str | None:
    text = str(value).strip()
    if text.casefold() in {"insgesamt", "total", "all variants"}:
        return None
    compact = re.sub(r"[-\s]", "", text)
    match = re.search(r"(G(?:R|k|\d)L(?:k|\d)W(?:k|\d))", compact, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Unrecognised GENESIS projection scenario: {value!r}")
    return match.group(1).upper()


def _normalise_population_rows(
    frame: pd.DataFrame,
    *,
    source_table: str,
    geography: str,
    value_column: str | None,
    unit_multiplier: float,
    topcode: int,
    scenario_label: str | None = None,
) -> pd.DataFrame:
    _, sex_label = _dimension(frame, "Geschlecht", "sex")
    _, age_label = _dimension(frame, "Altersjahre", "age")
    frame, selected_value = _select_value(
        frame,
        ("Bevölkerungsstand", "Bevoelkerungsstand", "population"),
        value_column,
    )
    quality_candidates = [
        f"{selected_value.rpartition('__')[0]}__q",
        f"{selected_value}__q",
    ]
    quality_column = next((column for column in quality_candidates if column in frame), None)
    rows = pd.DataFrame(
        {
            "year": _years(frame["time"]),
            "geography": geography,
            "sex": frame[sex_label].map(_sex),
            "age": frame[age_label].map(_single_age),
            "population": parse_value(frame[selected_value]) * unit_multiplier,
            "quality_flag": (
                frame[quality_column].astype(str).str.strip() if quality_column is not None else ""
            ),
            "source_table": source_table,
        }
    )
    if scenario_label is not None:
        rows["scenario"] = frame[scenario_label].map(_scenario)
    rows = rows.loc[rows["sex"].notna() & rows["age"].notna()].copy()
    if scenario_label is not None:
        rows = rows.loc[rows["scenario"].notna()].copy()
    rows["age_group"] = (
        rows["age"].astype(int).map(lambda age: diagnosis_age_group(age, topcode=topcode))
    )
    missing_value = frame.loc[rows.index, selected_value].astype(str).str.strip()
    rows.loc[rows["population"].isna() & rows["quality_flag"].eq(""), "quality_flag"] = (
        missing_value
    )
    keys = ["year", "geography", "sex", "age_group", "source_table"]
    if scenario_label is not None:
        keys.insert(4, "scenario")

    def complete_sum(values: pd.Series) -> float:
        return float(values.sum()) if values.notna().all() else float("nan")

    return (
        rows.groupby(keys, as_index=False, observed=True, dropna=False)
        .agg(
            population=("population", complete_sum),
            quality_flag=("quality_flag", _combine_quality),
        )
        .sort_values(keys)
        .reset_index(drop=True)
    )


def normalize_population_observed_ffcsv(
    frame: pd.DataFrame,
    *,
    source_table: str = "12411-0006",
    geography: str = "Germany",
    value_column: str | None = None,
    unit_multiplier: float = 1.0,
    topcode: int = 85,
    census_basis: str | None = None,
) -> pd.DataFrame:
    """Normalize observed national population rows and harmonize age bands."""

    rows = _normalise_population_rows(
        frame,
        source_table=source_table,
        geography=geography,
        value_column=value_column,
        unit_multiplier=unit_multiplier,
        topcode=topcode,
    )
    if census_basis is None:
        rows["census_basis"] = rows["year"].map(
            lambda year: (
                "Zensus 2022"
                if year >= 2022
                else "Zensus 2011"
                if year >= 2011
                else "pre-Zensus 2011 basis"
            )
        )
    else:
        rows["census_basis"] = census_basis
    return rows


def normalize_population_projected_ffcsv(
    frame: pd.DataFrame,
    *,
    source_table: str = "12421-0002",
    geography: str = "Germany",
    value_column: str | None = None,
    unit_multiplier: float = 1000.0,
    topcode: int = 85,
    projection_vintage: str = "16th coordinated projection; base 2024",
) -> pd.DataFrame:
    """Normalize projected population rows, scenarios and age bands."""

    _, scenario_label = _dimension(
        frame,
        "Varianten der Bevölkerungsvorausberechnung",
        "scenario",
        "variant",
    )
    rows = _normalise_population_rows(
        frame,
        source_table=source_table,
        geography=geography,
        value_column=value_column,
        unit_multiplier=unit_multiplier,
        topcode=topcode,
        scenario_label=scenario_label,
    )
    rows["projection_vintage"] = projection_vintage
    return rows
