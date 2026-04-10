"""Base classes for data quality validators.

Provides abstract base class and concrete validator implementations for
common data quality checks: completeness, uniqueness, null values, and range validation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd


class DataQualityError(Exception):
    """Exception raised when data quality validation fails.

    This is a marker exception for data quality issues. Validators typically
    return dict results rather than raising exceptions for recoverable errors.
    """

    pass


class BaseValidator(ABC):
    """Abstract base class for all data quality validators.

    Subclasses must implement the validate method which returns a dict result
    rather than raising exceptions for flexible error handling.
    """

    @abstractmethod
    def validate(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Validate data quality and return result dict.

        Args:
            df: DataFrame to validate (read-only, never modified)
            **kwargs: Validator-specific parameters

        Returns:
            Dict with validation results including 'is_valid' boolean
        """
        pass

    def _create_result(self, is_valid: bool, **kwargs) -> Dict[str, Any]:
        """Helper to build consistent result dict.

        Args:
            is_valid: Overall validation pass/fail
            **kwargs: Additional result fields

        Returns:
            Dict with is_valid and all extra fields
        """
        result = {"is_valid": is_valid}
        result.update(kwargs)
        return result


class CompletenessValidator(BaseValidator):
    """Validator for checking data completeness (expected record count).

    Checks if a DataFrame contains the expected number of records.
    """

    def validate(self, df: pd.DataFrame, expected_count: Optional[int] = None) -> Dict[str, Any]:
        """Validate DataFrame has expected number of records.

        Args:
            df: DataFrame to check
            expected_count: Expected number of records. If None, only returns actual_count.

        Returns:
            Dict with:
                - is_valid: bool
                - actual_count: int
                - expected_count: int or None
                - missing_pct: float (percentage of expected records missing)
        """
        actual_count = len(df)

        if expected_count is None:
            return self._create_result(
                is_valid=True,
                actual_count=actual_count,
                expected_count=None,
                missing_pct=0.0,
            )

        is_valid = actual_count >= expected_count
        missing_pct = max(0.0, (expected_count - actual_count) / expected_count * 100) if expected_count > 0 else 0.0

        return self._create_result(
            is_valid=is_valid,
            actual_count=actual_count,
            expected_count=expected_count,
            missing_pct=round(missing_pct, 2),
        )


class UniquenessValidator(BaseValidator):
    """Validator for checking uniqueness of key column combinations.

    Checks if specified columns have unique values (no duplicates).
    """

    def validate(self, df: pd.DataFrame, key_cols: Optional[List[str]] = None) -> Dict[str, Any]:
        """Validate uniqueness of key columns.

        Args:
            df: DataFrame to check
            key_cols: List of column names to check for uniqueness.
                      If None, uses all columns.

        Returns:
            Dict with:
                - is_valid: bool
                - has_duplicates: bool
                - duplicate_count: int (number of duplicate rows)
                - duplicate_keys: list of duplicate key values
        """
        if key_cols is None:
            key_cols = df.columns.tolist()

        # Validate columns exist
        missing_cols = set(key_cols) - set(df.columns)
        if missing_cols:
            return self._create_result(
                is_valid=False,
                has_duplicates=False,
                duplicate_count=0,
                duplicate_keys=[],
                error=f"Columns not found: {missing_cols}",
            )

        # Check for duplicates
        duplicates = df[key_cols].duplicated(keep=False)
        duplicate_count = duplicates.sum()
        duplicate_keys = df[duplicates][key_cols].drop_duplicates().to_dict("records")

        is_valid = duplicate_count == 0

        return self._create_result(
            is_valid=is_valid,
            has_duplicates=duplicate_count > 0,
            duplicate_count=int(duplicate_count),
            duplicate_keys=duplicate_keys[:100],  # Limit to first 100 for readability
        )


class NullCheckValidator(BaseValidator):
    """Validator for checking null values in required columns.

    Checks if specified columns contain any null/missing values.
    """

    def validate(self, df: pd.DataFrame, required_cols: Optional[List[str]] = None) -> Dict[str, Any]:
        """Validate required columns have no null values.

        Args:
            df: DataFrame to check
            required_cols: List of column names that must not contain nulls.
                          If None, checks all columns.

        Returns:
            Dict with:
                - is_valid: bool
                - null_columns: list of column names with nulls
                - null_counts: dict mapping column name to null count
        """
        if required_cols is None:
            required_cols = df.columns.tolist()

        # Validate columns exist
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            return self._create_result(
                is_valid=False,
                null_columns=list(missing_cols),
                null_counts={},
                error=f"Columns not found: {missing_cols}",
            )

        null_counts = {}
        null_columns = []

        for col in required_cols:
            col_nulls = df[col].isnull().sum()
            if col_nulls > 0:
                null_columns.append(col)
                null_counts[col] = int(col_nulls)

        is_valid = len(null_columns) == 0

        return self._create_result(
            is_valid=is_valid,
            null_columns=null_columns,
            null_counts=null_counts,
        )


class RangeValidator(BaseValidator):
    """Validator for checking if values are within an expected range.

    Checks if a column's values fall between min_val and max_val.
    """

    def validate(
        self,
        df: pd.DataFrame,
        col: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Validate column values are within range.

        Args:
            df: DataFrame to check
            col: Column name to validate
            min_val: Minimum allowed value (inclusive). If None, no lower bound.
            max_val: Maximum allowed value (inclusive). If None, no upper bound.

        Returns:
            Dict with:
                - is_valid: bool
                - out_of_range_count: int
                - sample_violations: list of dicts with row index and value
        """
        if col not in df.columns:
            return self._create_result(
                is_valid=False,
                out_of_range_count=0,
                sample_violations=[],
                error=f"Column not found: {col}",
            )

        # Get non-null values for checking
        mask = pd.Series([True] * len(df), index=df.index)

        if min_val is not None:
            mask = mask & (df[col] >= min_val)

        if max_val is not None:
            mask = mask & (df[col] <= max_val)

        out_of_range = ~mask
        out_of_range_count = out_of_range.sum()

        # Get sample violations (rows that failed validation)
        violations_df = df[out_of_range][[col]].reset_index()
        violations_df.columns = ["index", col]
        sample_violations = violations_df.head(100).to_dict("records")

        is_valid = out_of_range_count == 0

        return self._create_result(
            is_valid=is_valid,
            out_of_range_count=int(out_of_range_count),
            sample_violations=sample_violations,
        )
