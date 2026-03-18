import { execFile, execFileSync, spawn, ChildProcess } from "child_process";
import path from "path";
import fs from "fs";
import net from "net";
import log from "electron-log/main";
import { app } from "electron";

let child: ChildProcess | null = null;

const MAX_CRASHES = 3;
const CRASH_WINDOW_MS = 60_000;
const crashTimestamps: number[] = [];

/**
 * Resolve how to launch autohelper.
 *
 * Packaged: resources/autohelper/autohelper.exe (PyInstaller bundle)
 * Dev: run from source via `python -m autohelper.main --dev`
 *      Falls back to the frozen exe if the source tree isn't found.
 */
function getAutoHelperCommand(): { exe: string; args: string[]; cwd?: string } {
  if (app.isPackaged) {
    return {
      exe: path.join(process.resourcesPath, "autohelper", "autohelper.exe"),
      args: [],
    };
  }

  // Dev — prefer running from source so code changes take effect immediately
  const sourceDir = path.resolve(__dirname, "..", "..", "..", "autohelper");
  const mainPy = path.join(sourceDir, "autohelper", "main.py");

  if (fs.existsSync(mainPy)) {
    // Resolve the real python.exe — on Windows "python" may be a launcher shim
    // (Windows Store alias / py.exe) that spawns the real interpreter and exits
    // immediately with code 15, leaving an orphan we can't track.
    let pythonExe = "python";
    try {
      pythonExe = execFileSync("python", ["-c", "import sys; print(sys.executable)"], {
        encoding: "utf-8",
      }).trim();
      log.info("Resolved real Python: %s", pythonExe);
    } catch (err) {
      log.warn("Could not resolve real python.exe, using 'python': %s", err);
    }

    log.info("Dev mode: running AutoHelper from source at %s", sourceDir);
    return {
      exe: pythonExe,
      args: ["-u", "-m", "autohelper.main", "--dev"],
      cwd: sourceDir,
    };
  }

  // Fallback to frozen exe
  const exePath = path.resolve(__dirname, "..", "..", "autohelper", "autohelper.exe");
  log.info("Dev mode: source not found, falling back to frozen exe at %s", exePath);
  return { exe: exePath, args: [] };
}

/**
 * Check if a port is already in use.
 */
function isPortInUse(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const sock = new net.Socket();
    sock.setTimeout(1000);
    sock.once("connect", () => {
      sock.destroy();
      resolve(true);
    });
    sock.once("error", () => resolve(false));
    sock.once("timeout", () => {
      sock.destroy();
      resolve(false);
    });
    sock.connect(port, "127.0.0.1");
  });
}

/**
 * Find and kill the process using the given port (Windows only).
 * Returns true if a process was killed.
 */
function killProcessOnPort(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    if (process.platform !== "win32") {
      resolve(false);
      return;
    }
    // Find PID using netstat
    execFile("cmd", ["/c", `netstat -ano | findstr :${port} | findstr LISTENING`], (err, stdout) => {
      if (err || !stdout.trim()) {
        resolve(false);
        return;
      }
      // Parse PID from netstat output (last column)
      const pids = new Set<string>();
      for (const line of stdout.trim().split("\n")) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && pid !== "0") pids.add(pid);
      }
      if (pids.size === 0) {
        resolve(false);
        return;
      }
      let killed = 0;
      for (const pid of pids) {
        log.info("Killing stale process on port %d (PID %s)", port, pid);
        execFile("taskkill", ["/F", "/T", "/PID", pid], (killErr) => {
          killed++;
          if (killErr) log.warn("taskkill PID %s failed: %s", pid, killErr.message);
          if (killed === pids.size) resolve(true);
        });
      }
    });
  });
}

/**
 * Spawn autohelper as a child process.
 *
 * Packaged mode: skips if port 8100 is already in use.
 * Dev mode: kills any existing process on port 8100 first to guarantee
 *           we always run from the latest source code.
 */
export async function spawnAutoHelper(): Promise<void> {
  const portBusy = await isPortInUse(8100);

  if (portBusy && app.isPackaged) {
    log.info("Port 8100 already in use — skipping spawn (packaged mode)");
    return;
  }

  if (portBusy && !app.isPackaged) {
    log.warn("Port 8100 occupied — killing stale process to spawn fresh from source");
    await killProcessOnPort(8100);
    // Wait for port to be released
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
      if (!(await isPortInUse(8100))) break;
      await new Promise((r) => setTimeout(r, 300));
    }
    if (await isPortInUse(8100)) {
      log.error("Port 8100 still occupied after kill — cannot spawn from source");
      return;
    }
    log.info("Port 8100 cleared");
  }

  const cmd = getAutoHelperCommand();
  log.info(`Spawning: ${cmd.exe} ${cmd.args.join(" ")}${cmd.cwd ? ` (cwd: ${cmd.cwd})` : ""}`);

  child = spawn(cmd.exe, cmd.args, {
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    cwd: cmd.cwd,
  });

  child.stdout?.on("data", (data: Buffer) => {
    log.info(`[autohelper] ${data.toString().trimEnd()}`);
  });

  child.stderr?.on("data", (data: Buffer) => {
    log.warn(`[autohelper] ${data.toString().trimEnd()}`);
  });

  child.on("exit", (code, signal) => {
    log.info(`autohelper exited (code=${code}, signal=${signal})`);
    child = null;

    // Crash-restart with backoff
    const now = Date.now();
    crashTimestamps.push(now);
    // Prune old timestamps
    while (crashTimestamps.length > 0 && now - crashTimestamps[0] > CRASH_WINDOW_MS) {
      crashTimestamps.shift();
    }

    if (crashTimestamps.length <= MAX_CRASHES) {
      log.info("Restarting autohelper...");
      spawnAutoHelper().catch((err) => log.error("Restart failed:", err));
    } else {
      log.error(
        `autohelper crashed ${MAX_CRASHES} times in ${CRASH_WINDOW_MS / 1000}s — not restarting`,
      );
    }
  });
}

/**
 * Poll the health endpoint until it responds 200 or timeout.
 */
export async function waitForHealth(
  url: string,
  timeoutMs = 30_000,
  intervalMs = 500,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    try {
      const ok = await fetch(url).then((r) => r.ok);
      if (ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Health check timed out after ${timeoutMs}ms`);
}

/**
 * Kill the child process.
 */
export function killAutoHelper(): void {
  if (!child) return;

  const pid = child.pid;
  log.info(`Killing autohelper (pid=${pid})`);

  try {
    child.kill();
  } catch {
    // ignore
  }

  // Fallback: taskkill on Windows
  if (pid && process.platform === "win32") {
    try {
      execFile("taskkill", ["/F", "/PID", String(pid)], (err) => {
        if (err) log.warn("taskkill fallback failed:", err.message);
      });
    } catch {
      // best effort
    }
  }

  child = null;
}
