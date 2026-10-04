"""Load Etymological WordNet TSV files and prepare their edge attributes."""

import csv
from pathlib import Path
from typing import Optional

import pandas as pd

from polyphasia.constants import (
    EDGE_LIST_COLUMN_NAMES,
    INVALID_RELATIONSHIP_TYPE_MAP,
    LANGUAGE_PREFIX_TAG,
    RELATIONSHIP_TYPE_DIRECTION_MAP,
    RELATIVE_PATH_TO_SOURCE,
    EdgeDirections,
    ParsedColumnNames,
    SourceColumnNames,
)


def load_to_pandas(source_file: Optional[Path] = None) -> pd.DataFrame:
    """Read a headerless UTF-8 TSV with source, relationship, and target columns.

    The default is ``data/raw/etymologies.tsv`` relative to the working directory.
    Pass an explicit path when calling from notebooks or another directory.
    Quotes and strings such as ``NA`` are literal data, not CSV quoting or nulls.
    Empty files return the expected three-column schema. Malformed rows raise
    ``ValueError``; missing files retain the usual ``FileNotFoundError``.
    NUL bytes are rejected before parsing so they cannot silently truncate fields.
    """
    if source_file is None:
        source_file = RELATIVE_PATH_TO_SOURCE
    try:
        with open(source_file, "rb") as source:
            # The fast C parser silently truncates fields at NUL bytes. Check
            # the same file handle first, without retaining the corpus in memory.
            while chunk := source.read(1024 * 1024):
                if b"\x00" in chunk:
                    raise ValueError("TSV input must not contain NUL bytes")
            source.seek(0)
            data_frame = pd.read_csv(
                source,
                sep="\t",
                header=None,
                dtype=str,
                encoding="utf-8",
                keep_default_na=False,
                quoting=csv.QUOTE_NONE,
            )
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=EDGE_LIST_COLUMN_NAMES)
    except pd.errors.ParserError as exc:
        raise ValueError("Expected exactly three tab-separated fields per row") from exc
    if data_frame.shape[1] != len(EDGE_LIST_COLUMN_NAMES):
        raise ValueError("Expected exactly three tab-separated fields per row")
    data_frame.columns = EDGE_LIST_COLUMN_NAMES
    _validate_columns(data_frame)
    return data_frame


def _validate_columns(data_frame: pd.DataFrame) -> None:
    """Require a nonempty, NUL-free string in each source field."""
    missing = set(EDGE_LIST_COLUMN_NAMES).difference(data_frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if not data_frame.columns.is_unique:
        raise ValueError("Column names must be unique")
    for column in EDGE_LIST_COLUMN_NAMES:
        values = data_frame[column]
        if not values.map(
            lambda value: isinstance(value, str) and bool(value.strip())
        ).all():
            raise ValueError(f"{column} must contain nonempty strings")
        if values.map(lambda value: "\x00" in value).any():
            raise ValueError(f"{column} must not contain NUL characters")


def clean_data_frame(
    data_frame: pd.DataFrame, drop_rel_types: bool = True
) -> pd.DataFrame:
    """Return a cleaned copy with source/target language and word attributes.

    Each endpoint must have the form ``language: word`` with nonempty parts.
    Split only at the first ``: `` so punctuation and category tags in words
    are preserved. Invalid endpoints raise ``ValueError``, even in rows that
    would later be filtered out. Empty inputs retain the full output schema.

    Correct known relationship aliases in ``edge_type`` only. By default keep
    just ``rel:etymological_origin_of`` and ``rel:has_derived_form`` (root to
    derivative); set ``drop_rel_types=False`` to retain all relationship types.
    Neither the caller's data nor its index is modified.
    """
    _validate_columns(data_frame)
    cleaned = data_frame.copy()
    edge_type = SourceColumnNames.EDGE_TYPE.value
    cleaned[edge_type] = cleaned[edge_type].replace(INVALID_RELATIONSHIP_TYPE_MAP)

    for node_column, language_column, word_column in (
        (
            SourceColumnNames.SOURCE_NODE.value,
            ParsedColumnNames.SOURCE_LANGUAGE.value,
            ParsedColumnNames.SOURCE_WORD.value,
        ),
        (
            SourceColumnNames.TARGET_NODE.value,
            ParsedColumnNames.TARGET_LANGUAGE.value,
            ParsedColumnNames.TARGET_WORD.value,
        ),
    ):
        parts = (
            cleaned[node_column]
            .astype("string")
            .str.split(LANGUAGE_PREFIX_TAG, n=1, expand=True, regex=False)
            .reindex(columns=[0, 1])
            .astype("string")
        )
        valid = parts[0].str.fullmatch(r"[^\s:]+", na=False) & (
            parts[1].str.strip().str.len().fillna(0) > 0
        )
        if not valid.all():
            raise ValueError(
                f"{node_column} must use 'language: word' with nonempty parts"
            )
        cleaned[language_column] = parts[0]
        cleaned[word_column] = parts[1]

    if drop_rel_types:
        from_root_relationships = RELATIONSHIP_TYPE_DIRECTION_MAP[
            EdgeDirections.FROM_ROOT
        ]
        cleaned = cleaned.loc[cleaned[edge_type].isin(from_root_relationships)].copy()
    return cleaned
