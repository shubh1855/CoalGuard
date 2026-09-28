from __future__ import annotations

import os
import time
import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    from_email: str
    to_emails: list[str]
    brevo_api_key: str
    cooldown_sec: float = 60.0

    @classmethod
    def from_env(cls) -> "AlertConfig":
        from_addr = os.environ.get("SAFESIGHT_FROM_EMAIL", "").strip()
        to_raw = os.environ.get("SAFESIGHT_TO_EMAIL", "").strip()
        api_key = os.environ.get("SAFESIGHT_BREVO_API_KEY", "").strip()
        cooldown = float(os.environ.get("SAFESIGHT_COOLDOWN_SEC", "60"))

        missing = [
            name
            for name, val in [
                ("SAFESIGHT_FROM_EMAIL", from_addr),
                ("SAFESIGHT_TO_EMAIL", to_raw),
                ("SAFESIGHT_BREVO_API_KEY", api_key),
            ]
            if not val
        ]
        if missing:
            raise EnvironmentError(
                f"Missing required .env variables: {', '.join(missing)}"
            )

        to_list = [a.strip() for a in to_raw.split(",") if a.strip()]
        return cls(
            from_email=from_addr,
            to_emails=to_list,
            brevo_api_key=api_key,
            cooldown_sec=cooldown,
        )


def _build_html(count: int, timestamp: str) -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#1a1a1a">
      <div style="max-width:520px;margin:0 auto;border:1px solid #e0e0e0;
                  border-radius:8px;overflow:hidden">
        <div style="background:#b91c1c;padding:16px 20px">
          <h2 style="margin:0;color:#fff">⚠ SafeSight Zone Intrusion Alert</h2>
        </div>
        <div style="padding:20px">
          <p>A <strong>restricted-zone intrusion</strong> has been detected.</p>
          <table style="border-collapse:collapse;width:100%">
            <tr style="background:#f9f9f9">
              <td style="padding:8px 12px;width:40%"><b>Time</b></td>
              <td style="padding:8px 12px">{timestamp}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px"><b>Workers in zone</b></td>
              <td style="padding:8px 12px">{count}</td>
            </tr>
          </table>
          <p style="margin-top:20px;color:#555;font-size:0.9em">
            Automated alert from SafeSight. Please review the live feed immediately.
          </p>
        </div>
        <div style="background:#f3f4f6;padding:10px 20px;
                    font-size:0.8em;color:#6b7280">
          SafeSight Industrial Safety Dashboard
        </div>
      </div>
    </body></html>
    """


def _build_plain(count: int, timestamp: str) -> str:
    return (
        f"[SafeSight] Zone Intrusion Alert\n\n"
        f"Time           : {timestamp}\n"
        f"Workers in zone: {count}\n\n"
        f"Please review the live safety feed immediately."
    )


def _send_brevo(cfg: AlertConfig, subject: str, html: str, plain: str) -> None:
    payload = {
        "sender": {"email": cfg.from_email},
        "to": [{"email": addr} for addr in cfg.to_emails],
        "subject": subject,
        "htmlContent": html,
        "textContent": plain,
    }

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": cfg.brevo_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.getcode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Brevo HTTP {exc.code}: {body}") from exc

    if status not in (200, 201):
        raise RuntimeError(f"Brevo returned unexpected status {status}")

    logger.info("Zone intrusion alert sent via Brevo to %s", cfg.to_emails)


class ZoneIntrusionAlerter:

    def __init__(self, config: AlertConfig):
        self.cfg = config
        self._last_sent_at: float = 0.0

    @classmethod
    def from_env(cls) -> "ZoneIntrusionAlerter":
        return cls(AlertConfig.from_env())

    def notify_if_needed(self, result) -> bool:
        """
        Call once per frame. Fires an email when zone_intrusion_count > 0
        and the cooldown has elapsed. Returns True if an email was sent.
        """
        if result.zone_intrusion_count == 0:
            return False

        now = time.time()
        if now - self._last_sent_at < self.cfg.cooldown_sec:
            return False

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        count = result.zone_intrusion_count
        subject = f"[SafeSight] ⚠ Zone Intrusion — {count} worker(s) detected"

        _send_brevo(
            self.cfg,
            subject,
            _build_html(count, timestamp),
            _build_plain(count, timestamp),
        )
        self._last_sent_at = now
        return True

    @property
    def cooldown_remaining(self) -> float:
        return max(0.0, self.cfg.cooldown_sec - (time.time() - self._last_sent_at))

    def reset_cooldown(self) -> None:
        self._last_sent_at = 0.0

