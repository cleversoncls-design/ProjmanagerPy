"""Convite de calendário (iCalendar, RFC 5545/5546) para a Agenda de
consultores → Google Calendar.

Decisão confirmada com o usuário: em vez de OAuth com o Google (que exigiria
domínio HTTPS, projeto no Google Cloud e aprovação do administrador do
Workspace), o sistema manda ao consultor, pelo SMTP que já existe, um
e-mail com um convite `.ics` (METHOD:REQUEST). O Google Calendar reconhece
o convite e coloca o evento na agenda do consultor. Remarcar reenvia o MESMO
`UID` com `SEQUENCE` maior (o Google atualiza o evento em vez de duplicar) e
excluir manda METHOD:CANCEL.

Os horários dos agendamentos são "de parede" (sem fuso) no banco; o fuso em
que eles valem vem de `APP_TIMEZONE` (padrão America/Asuncion) e o convite
sai em UTC (sufixo `Z`), o que dispensa o bloco VTIMEZONE.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/Asuncion"


def app_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("APP_TIMEZONE") or DEFAULT_TIMEZONE)


def wall_clock_to_utc(day: date, at: time) -> datetime:
    """Interpreta (data, hora) no fuso da aplicação e devolve em UTC."""
    local = datetime.combine(day, at).replace(tzinfo=app_timezone())
    return local.astimezone(timezone.utc)


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line: str) -> str:
    """Quebra linhas longas em 75 octetos (RFC 5545 §3.1), com CRLF + espaço."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts: list[str] = []
    current = b""
    limit = 75
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > limit:
            parts.append(current.decode("utf-8"))
            current = b""
            limit = 74  # o espaço de continuação conta como 1 octeto
        current += encoded
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _fmt_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_invite_ics(
    *,
    method: str,
    uid: str,
    sequence: int,
    start_utc: datetime,
    end_utc: datetime,
    summary: str,
    description: str,
    organizer_email: str,
    organizer_name: str | None,
    attendee_email: str,
    attendee_name: str | None,
    now: datetime | None = None,
) -> str:
    """Monta o texto do `.ics`. `method` é "REQUEST" (criar/atualizar) ou
    "CANCEL" (excluir). O remetente do e-mail e o ORGANIZER precisam ser o
    mesmo endereço — o Google desconfia de convite cujo organizador difere
    de quem enviou."""
    if method not in {"REQUEST", "CANCEL"}:
        raise ValueError("method deve ser REQUEST ou CANCEL")
    stamp = _fmt_utc(now or datetime.now(timezone.utc))
    organizer_cn = f";CN={_quote_param(organizer_name)}" if organizer_name else ""
    attendee_cn = f";CN={_quote_param(attendee_name)}" if attendee_name else ""
    if method == "REQUEST":
        attendee = f"ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE{attendee_cn}:mailto:{attendee_email}"
        status_line = "STATUS:CONFIRMED"
    else:
        attendee = f"ATTENDEE;ROLE=REQ-PARTICIPANT{attendee_cn}:mailto:{attendee_email}"
        status_line = "STATUS:CANCELLED"
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//ProjmanagerPy//Agenda de consultores//PT",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{_fmt_utc(start_utc)}",
        f"DTEND:{_fmt_utc(end_utc)}",
        f"SEQUENCE:{sequence}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        status_line,
        "TRANSP:OPAQUE",
        f"ORGANIZER{organizer_cn}:mailto:{organizer_email}",
        attendee,
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def _quote_param(value: str) -> str:
    cleaned = value.replace('"', "'").replace("\r", " ").replace("\n", " ")
    return f'"{cleaned}"'
