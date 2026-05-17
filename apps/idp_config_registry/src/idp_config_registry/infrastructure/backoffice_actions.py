from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from idp_config_registry.application.errors import (
    AgentNotFoundError,
    ConfigRenderError,
    DuplicateConfigOutboxRecordError,
    DuplicateConfigRevisionError,
)
from idp_config_registry.application.use_cases.config_outbox import (
    MarkConfigOutboxDeadLetter,
    MarkConfigOutboxDeadLetterCommand,
    MarkConfigOutboxRetry,
    MarkConfigOutboxRetryCommand,
)
from idp_config_registry.application.use_cases.render_config import (
    RenderAgentRuntimeConfig,
    RenderAgentRuntimeConfigCommand,
    StoreRenderedAgentRuntimeConfig,
)
from idp_config_registry.infrastructure.backoffice_support import (
    format_datetime,
    get_request_state,
    optional_string,
    parse_issued_at,
)


@dataclass(frozen=True)
class AgentRenderTarget:
    tenant_code: str
    asset_code: str
    agent_code: str


@dataclass(frozen=True)
class RenderAgentRuntimeConfigResult:
    target: AgentRenderTarget
    config_revision: str
    outbox_record_count: int


@dataclass(frozen=True)
class RenderAgentRuntimeConfigFailure:
    target: AgentRenderTarget
    detail: str


class ConfigOutboxActionsBackofficeView(BaseView):
    name = "Config Outbox Actions"
    icon = "fa-solid fa-triangle-exclamation"

    @expose("/config-outbox/retry", methods=["POST"])
    async def retry_outbox_record(self, request: Request) -> JSONResponse:
        payload = await request.json()
        if not isinstance(payload, dict):
            return JSONResponse(
                {"detail": "Request body must be a JSON object"},
                status_code=422,
            )
        try:
            now = datetime.now(UTC)
            record = await MarkConfigOutboxRetry(
                get_request_state(request).unit_of_work_factory()
            ).execute(
                MarkConfigOutboxRetryCommand(
                    outbox_id=UUID(str(payload["outbox_id"])),
                    now=now,
                    error=optional_string(payload.get("reason"))
                    or "Manual backoffice retry",
                    next_attempt_at=parse_issued_at(
                        payload.get("next_attempt_at") or format_datetime(now)
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        if record is None:
            return JSONResponse({"detail": "Outbox record not found"}, status_code=404)
        return JSONResponse(outbox_action_payload(record), status_code=200)

    @expose("/config-outbox/dead-letter", methods=["POST"])
    async def dead_letter_outbox_record(self, request: Request) -> JSONResponse:
        payload = await request.json()
        if not isinstance(payload, dict):
            return JSONResponse(
                {"detail": "Request body must be a JSON object"},
                status_code=422,
            )
        try:
            record = await MarkConfigOutboxDeadLetter(
                get_request_state(request).unit_of_work_factory()
            ).execute(
                MarkConfigOutboxDeadLetterCommand(
                    outbox_id=UUID(str(payload["outbox_id"])),
                    now=datetime.now(UTC),
                    error=optional_string(payload.get("reason"))
                    or "Manual backoffice dead-letter",
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        if record is None:
            return JSONResponse({"detail": "Outbox record not found"}, status_code=404)
        return JSONResponse(outbox_action_payload(record), status_code=200)


async def render_agent_config_for_agent(
    request: Request,
    *,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    issued_at: datetime | None = None,
) -> RenderAgentRuntimeConfigResult:
    resolved_issued_at = issued_at or datetime.now(UTC)
    state = get_request_state(request)
    rendered = await RenderAgentRuntimeConfig(
        state.unit_of_work_factory(),
        state.config_payload_validator,
    ).execute(
        RenderAgentRuntimeConfigCommand(
            tenant_code=tenant_code,
            asset_code=asset_code,
            agent_code=agent_code,
            config_revision=auto_config_revision(resolved_issued_at),
            issued_at=resolved_issued_at,
            source_config_revisions=None,
        )
    )
    await StoreRenderedAgentRuntimeConfig(
        state.unit_of_work_factory(),
        state.config_payload_validator,
    ).execute(rendered)
    agent_runtime_payload = rendered.agent_runtime_payload
    return RenderAgentRuntimeConfigResult(
        target=AgentRenderTarget(
            tenant_code=tenant_code,
            asset_code=asset_code,
            agent_code=agent_code,
        ),
        config_revision=str(agent_runtime_payload["config_revision"]),
        outbox_record_count=1 + len(rendered.source_payloads),
    )


async def render_agent_config_action_response(
    request: Request,
    *,
    agent_targets: list[AgentRenderTarget],
    back_url: str,
) -> HTMLResponse:
    if not agent_targets:
        return HTMLResponse(
            render_agent_config_results_html(
                successes=[],
                failures=[],
                back_url=back_url,
                summary_message="Выберите хотя бы одного агента, чтобы собрать config.",
            ),
            status_code=422,
        )

    successes: list[RenderAgentRuntimeConfigResult] = []
    failures: list[RenderAgentRuntimeConfigFailure] = []
    for target in agent_targets:
        try:
            result = await render_agent_config_for_agent(
                request,
                tenant_code=target.tenant_code,
                asset_code=target.asset_code,
                agent_code=target.agent_code,
            )
        except (
            AgentNotFoundError,
            ConfigRenderError,
            DuplicateConfigOutboxRecordError,
            DuplicateConfigRevisionError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            failures.append(
                RenderAgentRuntimeConfigFailure(
                    target=target,
                    detail=str(exc),
                )
            )
        else:
            successes.append(result)

    status_code = 200 if successes else 422
    return HTMLResponse(
        render_agent_config_results_html(
            successes=successes,
            failures=failures,
            back_url=back_url,
        ),
        status_code=status_code,
    )


def render_agent_config_results_html(
    *,
    successes: list[RenderAgentRuntimeConfigResult],
    failures: list[RenderAgentRuntimeConfigFailure],
    back_url: str,
    summary_message: str | None = None,
) -> str:
    total_outbox_records = sum(result.outbox_record_count for result in successes)
    summary = summary_message
    if summary is None:
        summary = (
            f"Успешно обработано агентов: {len(successes)}. "
            f"Создано записей в config_outbox: {total_outbox_records}."
        )
        if failures:
            summary += f" Ошибок: {len(failures)}."

    success_items = "\n".join(
        (
            "<li>"
            f"<strong>{html.escape(result.target.agent_code)}</strong>"
            f" ({html.escape(result.target.tenant_code)} / {html.escape(result.target.asset_code)})"
            f": revision={html.escape(result.config_revision)}, "
            f"outbox_records={result.outbox_record_count}"
            "</li>"
        )
        for result in successes
    )
    failure_items = "\n".join(
        (
            "<li>"
            f"<strong>{html.escape(failure.target.agent_code)}</strong>"
            f" ({html.escape(failure.target.tenant_code)} / {html.escape(failure.target.asset_code)})"
            f": {html.escape(failure.detail)}"
            "</li>"
        )
        for failure in failures
    )
    success_html = (
        f"""
    <section class="panel success">
      <h2>Успешно</h2>
      <ul>{success_items}</ul>
    </section>
"""
        if success_items
        else ""
    )
    failure_html = (
        f"""
    <section class="panel error">
      <h2>Ошибки</h2>
      <ul>{failure_items}</ul>
    </section>
"""
        if failure_items
        else ""
    )
    return f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Собрать config</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      color: #18202f;
      background: #f6f8fb;
    }}
    main {{
      max-width: 920px;
      background: #ffffff;
      border: 1px solid #d9e0ea;
      border-radius: 14px;
      padding: 1.5rem;
      box-shadow: 0 8px 24px rgba(24, 32, 47, 0.08);
    }}
    .summary {{
      padding: 1rem;
      border-radius: 12px;
      background: #eef5ff;
      border: 1px solid #c9defc;
      line-height: 1.5;
      margin-bottom: 1rem;
    }}
    .panel {{
      margin-top: 1rem;
      padding: 1rem;
      border-radius: 12px;
      border: 1px solid #d9e0ea;
      background: #f8fafc;
    }}
    .panel.success {{
      background: #ecfdf3;
      border-color: #a7f3c5;
    }}
    .panel.error {{
      background: #fff1f2;
      border-color: #fecdd3;
    }}
    h2 {{
      margin-top: 0;
      font-size: 1.05rem;
    }}
    ul {{
      margin: 0.75rem 0 0;
      padding-left: 1.25rem;
      line-height: 1.5;
    }}
    .back-link {{
      display: inline-block;
      margin-top: 1.25rem;
      text-decoration: none;
      border-radius: 999px;
      padding: 0.75rem 1.15rem;
      color: #ffffff;
      background: #1557c0;
      font-weight: 750;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Собрать config</h1>
    <p class="summary">{html.escape(summary)}</p>
    {success_html}
    {failure_html}
    <a class="back-link" href="{html.escape(back_url, quote=True)}">Вернуться в список</a>
  </main>
</body>
</html>
"""


def auto_config_revision(issued_at: datetime) -> str:
    issued_utc = issued_at.astimezone(UTC)
    return f"backoffice-{issued_utc.strftime('%Y%m%dT%H%M%S%fZ')}"


def outbox_action_payload(record: object) -> dict[str, object]:
    return {
        "outbox_id": str(getattr(record, "outbox_id")),
        "status": getattr(getattr(record, "status"), "value"),
        "attempt_count": getattr(record, "attempt_count"),
        "last_error": getattr(record, "last_error"),
    }
