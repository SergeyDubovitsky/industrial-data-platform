from __future__ import annotations

from typing import Annotated

from fastapi import Path

TenantCodePath = Annotated[str, Path(alias="tenant_id")]
AssetCodePath = Annotated[str, Path(alias="asset_id")]
AgentCodePath = Annotated[str, Path(alias="agent_id")]
SourceCodePath = Annotated[str, Path(alias="source_id")]
PointCodePath = Annotated[str, Path(alias="point_id")]
