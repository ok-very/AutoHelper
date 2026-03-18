import { Tray, Menu, nativeImage, app } from "electron";
import path from "path";
import log from "electron-log/main";
import { showWindow, setIsQuitting } from "./index";

let tray: Tray | null = null;
let pollTimer: ReturnType<typeof setInterval> | null = null;

// State
let statusLabel = "Status: Idle";
let connectionLabel = "Not paired";
let artistScanLabel = "";
let isWorking = false;

function getIconPath(name: string): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, name);
  }
  return path.join(__dirname, "..", "..", "resources", name);
}

function rebuildMenu(): void {
  if (!tray) return;

  const menu = Menu.buildFromTemplate([
    { label: "AutoHelper Service", enabled: false },
    { label: statusLabel, enabled: false },
    { label: connectionLabel, enabled: false },
    ...(artistScanLabel
      ? [{ label: artistScanLabel, enabled: false } as Electron.MenuItemConstructorOptions]
      : []),
    { type: "separator" },
    { label: "Open Dashboard", click: () => showWindow("/") },
    { label: "Settings", click: () => showWindow("/dashboard") },
    { type: "separator" },
    {
      label: "Exit",
      click: () => {
        setIsQuitting(true);
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(menu);
}

function updateIcon(): void {
  if (!tray) return;
  const iconFile = isWorking ? "tray-working.png" : "tray-idle.png";
  const icon = nativeImage.createFromPath(getIconPath(iconFile));
  tray.setImage(icon);
  tray.setToolTip(isWorking ? "AutoHelper — Working..." : "AutoHelper — Idle");
}

async function pollStatus(): Promise<void> {
  let menuDirty = false;

  // Poll runner + indexer status
  try {
    const [runnerRes, indexRes] = await Promise.all([
      fetch("http://127.0.0.1:8100/runner/status").then((r) => r.json()),
      fetch("http://127.0.0.1:8100/index/status").then((r) => r.json()),
    ]);
    const working =
      runnerRes?.active === true || indexRes?.status === "running";
    if (working !== isWorking) {
      isWorking = working;
      updateIcon();
      menuDirty = true;
    }

    const newStatus = working ? "Status: Working..." : "Status: Idle";
    if (newStatus !== statusLabel) {
      statusLabel = newStatus;
      menuDirty = true;
    }
  } catch {
    // Service not reachable — keep current state
  }

  // Poll artist scan status
  try {
    const scanRes = await fetch(
      "http://127.0.0.1:8100/artists/scan/status",
    ).then((r) => r.json());
    let newScanLabel = "";
    if (scanRes?.is_scanning) {
      newScanLabel = "Artists: Scanning…";
    } else if (scanRes?.last_run?.status === "completed") {
      const count = scanRes.last_run.stats?.artists ?? "?";
      newScanLabel = `Artists: ${count} indexed`;
    }
    if (newScanLabel !== artistScanLabel) {
      artistScanLabel = newScanLabel;
      menuDirty = true;
    }
  } catch {
    // ignore
  }

  // Poll config for pairing state
  try {
    const cfg = await fetch("http://127.0.0.1:8100/config").then((r) =>
      r.json(),
    );
    const paired = !!cfg?.autoart_link_key;
    const newLabel = paired ? "Paired" : "Not paired";
    if (newLabel !== connectionLabel) {
      connectionLabel = newLabel;
      menuDirty = true;
    }
  } catch {
    // ignore
  }

  if (menuDirty) {
    rebuildMenu();
  }
}

export function setupTray(): void {
  const iconPath = getIconPath("tray-idle.png");
  const icon = nativeImage.createFromPath(iconPath);

  tray = new Tray(icon);
  tray.setToolTip("AutoHelper — Idle");

  tray.on("double-click", () => showWindow());

  rebuildMenu();

  // Start polling every 15 seconds
  pollStatus(); // initial
  pollTimer = setInterval(pollStatus, 15_000);

  log.info("Tray icon ready");
}

export function destroyTray(): void {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (tray) {
    tray.destroy();
    tray = null;
  }
}
