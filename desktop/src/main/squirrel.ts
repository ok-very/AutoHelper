/**
 * Squirrel.Windows lifecycle event handling.
 *
 * Squirrel invokes the app exe with special flags during install, update,
 * and uninstall. We must handle these synchronously and quit immediately.
 *
 * Events:
 *   --squirrel-install       → first install: create shortcuts, register startup
 *   --squirrel-updated       → after update: update shortcuts
 *   --squirrel-uninstall     → uninstalling: remove shortcuts, cleanup
 *   --squirrel-obsolete      → old version being replaced: quit immediately
 *   --squirrel-firstrun      → first launch after install (not a quit event)
 */

import { app } from "electron";
import { execFileSync } from "child_process";
import path from "path";
import fs from "fs";
import log from "electron-log/main";

const APP_NAME = "AutoHelper";

function getUpdateExe(): string {
  return path.resolve(path.dirname(process.execPath), "..", "Update.exe");
}

function runSquirrelCommand(...args: string[]): void {
  const updateExe = getUpdateExe();
  try {
    execFileSync(updateExe, args, { timeout: 15_000 });
  } catch (err) {
    log.error(`Squirrel command failed: ${args.join(" ")}`, err);
  }
}

function createShortcuts(): void {
  runSquirrelCommand("--createShortcut", path.basename(process.execPath));
}

function removeShortcuts(): void {
  runSquirrelCommand("--removeShortcut", path.basename(process.execPath));
}

function setLoginItemEnabled(enabled: boolean): void {
  app.setLoginItemSettings({
    openAtLogin: enabled,
    name: APP_NAME,
  });
}

function cleanupAppData(): void {
  // Remove AutoHelper's data directory on uninstall (best-effort)
  const appData = process.env.LOCALAPPDATA;
  if (!appData) return;

  const dataDir = path.join(appData, "autohelper");
  try {
    if (fs.existsSync(dataDir)) {
      fs.rmSync(dataDir, { recursive: true, force: true });
      log.info(`Cleaned up ${dataDir}`);
    }
  } catch {
    // best effort
  }
}

/**
 * Handle Squirrel lifecycle events. Returns true if the app should quit
 * immediately (all events except --squirrel-firstrun).
 */
export function handleSquirrelEvents(): boolean {
  if (process.platform !== "win32") return false;

  const squirrelArg = process.argv.find((arg) =>
    arg.startsWith("--squirrel-"),
  );
  if (!squirrelArg) return false;

  const event = squirrelArg.replace("--squirrel-", "");

  switch (event) {
    case "install":
      log.info("Squirrel: install");
      createShortcuts();
      setLoginItemEnabled(true);
      break;

    case "updated":
      log.info("Squirrel: updated");
      createShortcuts(); // update shortcuts to point to new version
      break;

    case "uninstall":
      log.info("Squirrel: uninstall");
      removeShortcuts();
      setLoginItemEnabled(false);
      cleanupAppData();
      break;

    case "obsolete":
      log.info("Squirrel: obsolete");
      break;

    case "firstrun":
      // Not a quit event — app should continue launching normally
      log.info("Squirrel: first run after install");
      return false;

    default:
      return false;
  }

  // All events except firstrun → quit immediately
  app.quit();
  return true;
}
