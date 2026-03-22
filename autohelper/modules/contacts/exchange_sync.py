"""Exchange Online sync via persistent PowerShell session.

One long-lived pwsh process handles Connect, Test, Sync, and Disconnect.
Python sends JSON commands via stdin; PowerShell writes JSON responses to stdout.
"""

import json
import logging
import queue
import re
import subprocess
import threading
import time
from pathlib import Path

from autohelper.config import get_settings

from .types import ContactRecord

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent / "powershell"
_SENTINEL = "###CMDEND###"


def _find_pwsh() -> str | None:
    """Find PowerShell 7+ executable."""
    import shutil
    return shutil.which("pwsh") or shutil.which("powershell")


# ── Persistent session ────────────────────────────────────────────


class ExchangeSession:
    """Singleton persistent PowerShell process for Exchange Online.

    Lifecycle:
        connect()    → spawns pwsh, device code auth, session stays alive
        test()       → sends test command to living process
        sync(...)    → sends sync operations to living process
        disconnect() → sends disconnect, kills process
    """

    _instance: "ExchangeSession | None" = None
    _init_lock = threading.Lock()

    def __new__(cls) -> "ExchangeSession":
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._proc: subprocess.Popen | None = None
        self._state = "disconnected"  # disconnected | connecting | connected
        self._device_code: dict | None = None
        self._connect_error: str | None = None
        self._response_queue: queue.Queue[str] = queue.Queue()
        self._cmd_lock = threading.Lock()
        self._connect_event = threading.Event()
        self._initialized = True

    @property
    def state(self) -> str:
        if self._proc and self._proc.poll() is not None:
            self._state = "disconnected"
        return self._state

    @property
    def is_connected(self) -> bool:
        return (
            self._state == "connected"
            and self._proc is not None
            and self._proc.poll() is None
        )

    # ── Connect ───────────────────────────────────────────────────

    def connect(self, email: str) -> dict:
        """Spawn persistent pwsh, start device code auth, return immediately."""
        if self.is_connected:
            return {"started": True, "connected": True, "message": "Already connected"}

        self._kill()

        pwsh = _find_pwsh()
        if not pwsh:
            return {"started": False, "message": "PowerShell 7 (pwsh) not found"}

        script = SCRIPTS_DIR / "exchange_session.ps1"
        if not script.exists():
            return {"started": False, "message": "exchange_session.ps1 not found"}

        self._state = "connecting"
        self._device_code = None
        self._connect_error = None
        self._connect_event.clear()
        # drain any stale responses
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                break

        self._proc = subprocess.Popen(
            [pwsh, "-ExecutionPolicy", "Bypass", "-File", str(script), "-Email", email],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        threading.Thread(target=self._read_stderr, daemon=True, name="exo-stderr").start()
        threading.Thread(target=self._read_stdout, daemon=True, name="exo-stdout").start()

        # Wait for device code on stderr or CONNECTED on stdout
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self._device_code:
                return {
                    "started": True,
                    "device_code": True,
                    "url": self._device_code["url"],
                    "code": self._device_code["code"],
                    "message": self._device_code["message"],
                }
            if self._state == "connected":
                return {"started": True, "connected": True, "message": "Connected (cached token)"}
            if self._connect_error:
                self._state = "disconnected"
                return {"started": False, "message": self._connect_error}
            if self._proc.poll() is not None:
                break
            time.sleep(0.2)

        self._state = "disconnected"
        return {"started": False, "message": "No device code received — check prerequisites"}

    # ── Background readers ────────────────────────────────────────

    def _read_stderr(self) -> None:
        """Log stderr output."""
        assert self._proc and self._proc.stderr
        for line in iter(self._proc.stderr.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            logger.info("exchange-stderr: %s", line)
            self._check_device_code(line)

    def _read_stdout(self) -> None:
        """Read stdout: detect CONNECTED/device code during connect, then queue command responses."""
        assert self._proc and self._proc.stdout
        for line in iter(self._proc.stdout.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            logger.info("exchange-stdout: %s", line)

            if self._state == "connecting":
                if line.startswith("CONNECTED:"):
                    org = line.split("CONNECTED:", 1)[1].strip()
                    self._state = "connected"
                    self._connect_event.set()
                    logger.info("Exchange session connected: %s", org)
                    continue
                if line.startswith("CONNECT_FAILED:"):
                    self._connect_error = line.split("CONNECT_FAILED:", 1)[1].strip()
                    self._state = "disconnected"
                    self._connect_event.set()
                    continue
                # Device code prompt can appear on stdout (MSAL writes here)
                if self._check_device_code(line):
                    continue

            # Command response line — queue it for send_command
            self._response_queue.put(line)

    def _check_device_code(self, line: str) -> bool:
        """Check a line for device code prompt. Returns True if found."""
        if self._device_code:
            return False
        url_m = re.search(r"(https://\S+/device\S*)", line)
        code_m = re.search(r"enter the code (\S+)", line)
        if url_m and code_m:
            self._device_code = {
                "url": url_m.group(1),
                "code": code_m.group(1),
                "message": f"Open {url_m.group(1)} and enter code {code_m.group(1)}",
            }
            return True
        return False

    # ── Command protocol ──────────────────────────────────────────

    def send_command(self, cmd: dict, timeout: float = 300) -> dict:
        """Send JSON command via stdin, read JSON response from stdout."""
        if not self.is_connected:
            return {"error": "Not connected"}

        with self._cmd_lock:
            assert self._proc and self._proc.stdin
            try:
                self._proc.stdin.write(json.dumps(cmd, ensure_ascii=False) + "\n")
                self._proc.stdin.flush()
            except (OSError, BrokenPipeError) as e:
                self._state = "disconnected"
                return {"error": f"Session died: {e}"}

            # Collect lines until sentinel
            lines: list[str] = []
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    remaining = max(0.1, deadline - time.monotonic())
                    line = self._response_queue.get(timeout=min(remaining, 5))
                except queue.Empty:
                    if self._proc.poll() is not None:
                        self._state = "disconnected"
                        return {"error": "Session process exited"}
                    continue
                if line == _SENTINEL:
                    break
                lines.append(line)
            else:
                return {"error": "Command timed out"}

            text = "\n".join(lines)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logger.error("Bad JSON from session: %s", text[:500])
                return {"error": f"Invalid response: {text[:200]}"}

    # ── High-level operations ─────────────────────────────────────

    def test(self) -> dict:
        if self._state == "connecting":
            return {"connected": False, "message": "Still connecting — complete MFA in browser"}
        if not self.is_connected:
            return {"connected": False, "message": "Not connected — use Connect first"}
        return self.send_command({"action": "test"}, timeout=15)

    def sync_batch(self, create: list, update: list, delete: list) -> dict:
        """Send one batch of sync operations."""
        if not self.is_connected:
            return {"created": 0, "updated": 0, "deleted": 0,
                    "errors": ["Not connected"]}
        return self.send_command(
            {"action": "sync", "create": create, "update": update, "delete": delete},
            timeout=600,
        )

    def disconnect(self) -> dict:
        if self.is_connected:
            try:
                self.send_command({"action": "disconnect"}, timeout=10)
            except Exception:
                pass
        self._kill()
        return {"ok": True, "message": "Exchange session disconnected"}

    # ── Process management ────────────────────────────────────────

    def _kill(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._state = "disconnected"
        self._device_code = None
        self._connect_error = None
        self._connect_event.clear()


# ── Public API (unchanged signatures for router + service) ────────


def get_session_state() -> dict:
    """Return the current session state for UI polling."""
    session = ExchangeSession()
    result: dict = {"state": session.state}
    if session._connect_error:
        result["error"] = session._connect_error
    return result


def check_exchange_prerequisites() -> dict:
    """Check if Exchange sync prerequisites are met."""
    pwsh = _find_pwsh()
    if not pwsh:
        return {"ready": False, "pwsh": False, "module": False,
                "pwsh_version": "", "module_version": "",
                "message": "PowerShell not found. Install from https://aka.ms/powershell-release?tag=stable"}

    try:
        r = subprocess.run([pwsh, "-Command", "$PSVersionTable.PSVersion.ToString()"],
                           capture_output=True, text=True, timeout=10)
        version = r.stdout.strip()
    except Exception:
        version = "unknown"

    try:
        r = subprocess.run(
            [pwsh, "-Command",
             "(Get-Module -ListAvailable ExchangeOnlineManagement).Version.ToString()"],
            capture_output=True, text=True, timeout=15)
        mod_version = r.stdout.strip()
        has_module = bool(mod_version)
    except Exception:
        mod_version = ""
        has_module = False

    ready = bool(pwsh) and has_module
    result = {
        "ready": ready,
        "pwsh": True,
        "module": has_module,
        "pwsh_version": version,
        "module_version": mod_version,
    }
    if not has_module:
        result["message"] = "ExchangeOnlineManagement module not installed. Run: pwsh -File scripts/setup-exchange.ps1"
    return result


_COUNTRY_TO_ISO = {
    "united states of america": "US",
    "united states": "US",
    "usa": "US",
    "canada": "CA",
    "united kingdom": "GB",
    "great britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "japan": "JP",
    "china": "CN",
    "india": "IN",
    "mexico": "MX",
    "brazil": "BR",
    "italy": "IT",
    "spain": "ES",
    "netherlands": "NL",
    "switzerland": "CH",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "new zealand": "NZ",
    "south korea": "KR",
    "singapore": "SG",
    "hong kong": "HK",
    "taiwan": "TW",
    "israel": "IL",
}


_ISO_COUNTRY_CODES = {
    "AD","AE","AF","AG","AI","AL","AM","AO","AQ","AR","AS","AT","AU","AW","AX","AZ",
    "BA","BB","BD","BE","BF","BG","BH","BI","BJ","BL","BM","BN","BO","BQ","BR","BS",
    "BT","BV","BW","BY","BZ","CA","CC","CD","CF","CG","CH","CI","CK","CL","CM","CN",
    "CO","CR","CU","CV","CW","CX","CY","CZ","DE","DJ","DK","DM","DO","DZ","EC","EE",
    "EG","EH","ER","ES","ET","FI","FJ","FK","FM","FO","FR","GA","GB","GD","GE","GF",
    "GG","GH","GI","GL","GM","GN","GP","GQ","GR","GS","GT","GU","GW","GY","HK","HM",
    "HN","HR","HT","HU","ID","IE","IL","IM","IN","IO","IQ","IR","IS","IT","JE","JM",
    "JO","JP","KE","KG","KH","KI","KM","KN","KP","KR","KW","KY","KZ","LA","LB","LC",
    "LI","LK","LR","LS","LT","LU","LV","LY","MA","MC","MD","ME","MF","MG","MH","MK",
    "ML","MM","MN","MO","MP","MQ","MR","MS","MT","MU","MV","MW","MX","MY","MZ","NA",
    "NC","NE","NF","NG","NI","NL","NO","NP","NR","NU","NZ","OM","PA","PE","PF","PG",
    "PH","PK","PL","PM","PN","PR","PS","PT","PW","PY","QA","RE","RO","RS","RU","RW",
    "SA","SB","SC","SD","SE","SG","SH","SI","SJ","SK","SL","SM","SN","SO","SR","SS",
    "ST","SV","SX","SY","SZ","TC","TD","TF","TG","TH","TJ","TK","TL","TM","TN","TO",
    "TR","TT","TV","TW","TZ","UA","UG","UM","US","UY","UZ","VA","VC","VE","VG","VI",
    "VN","VU","WF","WS","YE","YT","ZA","ZM","ZW",
}


def validate_contacts(contacts: list[ContactRecord]) -> list[str]:
    """Validate contacts for Exchange compatibility. Returns warning strings."""
    warnings: list[str] = []
    for c in contacts:
        if not c.email_primary:
            warnings.append(f"Missing email: {c.full_name or '(no name)'}")
        if c.country:
            normalized = _COUNTRY_TO_ISO.get(c.country.lower(), c.country)
            if normalized.upper() not in _ISO_COUNTRY_CODES:
                warnings.append(f"Unmapped country '{c.country}' on {c.email_primary}")
        display = c.full_name or c.email_primary
        if display and len(display) > 256:
            warnings.append(f"DisplayName too long ({len(display)} chars) on {c.email_primary}")
    return warnings


def _build_exchange_contact(contact: ContactRecord, managed_prefix: str) -> dict:
    """Map a ContactRecord to Exchange Online contact properties."""
    country = contact.country
    if country:
        country = _COUNTRY_TO_ISO.get(country.lower(), country)
    return {
        "Identity": f"{managed_prefix}{contact.email_primary}",
        "DisplayName": contact.full_name or contact.email_primary,
        "ExternalEmailAddress": contact.email_primary,
        "FirstName": contact.first_name,
        "LastName": contact.last_name,
        "Company": contact.company,
        "Title": contact.job_title,
        "Phone": contact.phone_business,
        "MobilePhone": contact.phone_mobile,
        "StreetAddress": contact.street_address,
        "City": contact.city,
        "StateOrProvince": contact.state,
        "PostalCode": contact.postal_code,
        "CountryOrRegion": country,
        "CustomAttribute1": contact.category_canonical,
    }


def connect_exchange_interactive() -> dict:
    """Start device code auth via persistent session."""
    settings = get_settings()
    email = getattr(settings, "exchange_email", "")
    if not email:
        return {"started": False, "message": "No exchange_email configured"}
    return ExchangeSession().connect(email)


def test_exchange_connection() -> dict:
    """Test connection via persistent session."""
    return ExchangeSession().test()


def disconnect_exchange() -> dict:
    """Disconnect persistent session."""
    return ExchangeSession().disconnect()


def sync_contacts_to_exchange(
    to_create: list[ContactRecord],
    to_update: list[ContactRecord],
    to_delete: list[str],
    managed_prefix: str,
    batch_size: int = 50,
) -> dict:
    """Push contacts to Exchange via the persistent session, in batches."""
    session = ExchangeSession()
    if not session.is_connected:
        return {"created": 0, "updated": 0, "deleted": 0,
                "errors": ["Not connected to Exchange — use Connect first"]}

    all_creates = [_build_exchange_contact(c, managed_prefix) for c in to_create]
    all_updates = [_build_exchange_contact(c, managed_prefix) for c in to_update]
    all_deletes = list(to_delete)

    totals: dict = {"created": 0, "updated": 0, "deleted": 0, "errors": []}
    max_len = max(len(all_creates), len(all_updates), len(all_deletes), 1)
    batch_num = 0

    from .service import ContactSyncService

    for offset in range(0, max_len, batch_size):
        # Check stop flag between batches
        if ContactSyncService()._stop_requested:
            logger.info("Exchange sync stopped by user after batch %d", batch_num)
            totals["errors"].append("Stopped by user")
            break

        batch_c = all_creates[offset:offset + batch_size]
        batch_u = all_updates[offset:offset + batch_size]
        batch_d = all_deletes[offset:offset + batch_size]

        if not batch_c and not batch_u and not batch_d:
            break

        batch_num += 1
        logger.info(
            "Exchange sync batch %d: %d create, %d update, %d delete",
            batch_num, len(batch_c), len(batch_u), len(batch_d),
        )

        result = session.sync_batch(batch_c, batch_u, batch_d)
        totals["created"] += result.get("created", 0)
        totals["updated"] += result.get("updated", 0)
        totals["deleted"] += result.get("deleted", 0)
        totals["errors"].extend(result.get("errors", []))

        if result.get("error"):
            totals["errors"].append(result["error"])
            break  # session died or timed out

    return totals
