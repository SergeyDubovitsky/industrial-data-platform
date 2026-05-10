from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EdgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenEdgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
