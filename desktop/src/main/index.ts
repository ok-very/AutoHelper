import nodePath from "node:path";
import { app, BrowserWindow, dialog, ipcMain, Menu, session, shell } from "electron";
import log from "electron-log/main";
import { handleSquirrelEvents } from "./squirrel";
import { spawnAutoHelper, killAutoHelper, waitForHealth } from "./child-process";
import { setupTray } from "./tray";

// Handle Squirrel install/update/uninstall events — must be first.
// During these events the app creates/removes shortcuts and quits immediately.
if (handleSquirrelEvents()) process.exit(0);

log.initialize();

// Remove the default menu bar (File, Edit, View, Window, Help)
Menu.setApplicationMenu(null);

// Dual mode: --mode=autoart points at the full AutoArt frontend,
// default (autohelper) points at the AutoHelper Python service.
const MODE = process.argv.includes("--mode=autoart") ? "autoart" : "autohelper";
const BASE_URL = MODE === "autoart"
  ? "http://127.0.0.1:3100"   // Full AutoArt frontend
  : "http://127.0.0.1:8100";  // AutoHelper only

let mainWindow: BrowserWindow | null = null;
let isQuitting = false;

export function getIsQuitting(): boolean {
  return isQuitting;
}

export function setIsQuitting(value: boolean): void {
  isQuitting = value;
}

/**
 * Show the main window, optionally navigating to a specific path.
 * @param path - URL path to load (default: "/dashboard")
 */
export async function showWindow(path: string = "/"): Promise<void> {
  const targetUrl = `${BASE_URL}${path}`;

  if (mainWindow && !mainWindow.isDestroyed()) {
    // If a different path is requested, navigate to it
    const currentUrl = mainWindow.webContents.getURL();
    if (!currentUrl.endsWith(path)) {
      mainWindow.loadURL(targetUrl);
    }
    mainWindow.show();
    mainWindow.focus();
    return;
  }

  // Always clear cache before creating a window so static assets are fresh
  await session.defaultSession.clearCache();
  await session.defaultSession.clearStorageData({ storages: ["cachestorage"] });

  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: nodePath.join(__dirname, "..", "preload", "index.js"),
    },
  });

  mainWindow.loadURL(targetUrl);

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  mainWindow.on("close", (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow?.hide();
    }
  });

  // Open external links in the default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

// ── IPC handlers ────────────────────────────────────────────────

ipcMain.handle("select-folder", async () => {
  const win = BrowserWindow.getFocusedWindow() ?? mainWindow;
  const result = await dialog.showOpenDialog(win!, {
    properties: ["openDirectory"],
    title: "Select folder",
  });
  return result.canceled ? null : result.filePaths[0];
});

// ── Single instance lock ─────────────────────────────────────────

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    showWindow();
  });

  app.whenReady().then(async () => {
    log.info("AutoHelper Desktop starting (mode=%s)...", MODE);

    // Clear HTTP cache so the webview always loads fresh static assets
    await session.defaultSession.clearCache();
    log.info("Cleared webview cache");

    try {
      await spawnAutoHelper();
      await waitForHealth("http://127.0.0.1:8100/health");
      // Log server mode so we always know what we're connected to
      try {
        const health = await fetch("http://127.0.0.1:8100/health").then((r) => r.json());
        log.info("AutoHelper service healthy — mode=%s, version=%s", health.mode, health.version);
      } catch {
        log.info("AutoHelper service is healthy (could not read mode)");
      }
    } catch (err) {
      log.error("Failed to start AutoHelper service:", err);
    }

    setupTray();
  });

  app.on("before-quit", () => {
    isQuitting = true;
    killAutoHelper();
  });

  // Keep the app running when all windows are closed (tray mode)
  app.on("window-all-closed", () => {
    // No-op: stay alive in tray mode
  });
}
