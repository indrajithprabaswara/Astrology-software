"""Persistence utilities for kundali data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import pandas as pd


@dataclass
class KundaliRecord:
    """Serializable record of kundali data."""

    metadata: Dict[str, Any]
    planetary_positions: pd.DataFrame
    divisional_positions: Dict[str, pd.DataFrame]
    strengths: Dict[str, Any]

    def to_json(self) -> Dict[str, Any]:
        """Convert the record to a JSON-serialisable structure."""

        return {
            "metadata": self.metadata,
            "planetary_positions": self.planetary_positions.to_dict(orient="records"),
            "divisional_positions": {
                name: df.to_dict(orient="records") for name, df in self.divisional_positions.items()
            },
            "strengths": self.strengths,
        }

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "KundaliRecord":
        """Construct a :class:`KundaliRecord` from JSON data."""

        return cls(
            metadata=payload.get("metadata", {}),
            planetary_positions=pd.DataFrame(payload.get("planetary_positions", [])),
            divisional_positions={
                name: pd.DataFrame(records) for name, records in payload.get("divisional_positions", {}).items()
            },
            strengths=payload.get("strengths", {}),
        )


def save_kundali(record: KundaliRecord, path: str | Path) -> None:
    """Save a kundali record to disk."""

    path = Path(path)
    path.write_text(json.dumps(record.to_json(), indent=2), encoding="utf-8")


def load_kundali(path: str | Path) -> KundaliRecord:
    """Load a kundali record from disk."""

    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return KundaliRecord.from_json(payload)
