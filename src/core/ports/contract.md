# Port Contracts

## DataPort

**Purpose**: Abstract interface for versioned time series data storage and retrieval

### Methods

#### `load(symbol, start_date?, end_date?, as_of_date?, version?) -> DataFrame`

Loads time series data with optional point-in-time filtering.

**Pre-conditions**:
- `symbol` must exist in data store

**Post-conditions**:
- Returns DataFrame with DatetimeIndex
- If `as_of_date` specified, no records with `published_date > as_of_date`

**Errors**:
- `DataNotFoundError`: Symbol or version not found
- `ValueError`: `as_of_date` in the future

#### `save(symbol, data, version, metadata) -> None`

Saves versioned time series data.

**Pre-conditions**:
- `data` must have DatetimeIndex
- `version` must not exist for symbol

**Post-conditions**:
- Data persisted with version tag
- Quality validation executed

**Errors**:
- `VersionExistsError`: Version already exists
- `DataQualityError`: Data fails validation

#### `query_versions(symbol) -> list[str]`

Lists available versions for a symbol.

**Errors**:
- `DataNotFoundError`: Symbol not found

#### `validate_data_quality(data) -> dict`

Validates data quality, returns report with pass/fail status.

### Implementations

- `ArcticDBAdapter`: Production implementation using ArcticDB
- `StubDataAdapter`: Test stub for unit testing
