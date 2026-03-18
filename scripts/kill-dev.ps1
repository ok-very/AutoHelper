# ===========================================
# AutoArt Kill Dev Processes (Windows)
# ===========================================
# Usage:
#   .\scripts\kill-dev.ps1
#   pnpm dev:kill

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\config.ps1"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  AutoArt Kill Dev Processes" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Stop any jobs created by scripts/dev.ps1 (only visible within the current PowerShell session)
$jobNames = @("AutoArt-Backend", "AutoArt-Frontend", "AutoArt-AutoHelper", "AutoArt-Forms", "AutoArt-Mail")
$jobs = Get-Job -ErrorAction SilentlyContinue | Where-Object { $jobNames -contains $_.Name }
if ($jobs) {
    Write-Host "[*] Stopping existing PowerShell jobs..." -ForegroundColor Yellow
    try {
        $jobs | Stop-Job -Force -ErrorAction SilentlyContinue
        $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Jobs stopped." -ForegroundColor Green
    }
    catch {
        Write-Host "[!] Failed stopping jobs: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "[*] Stopping listeners on dev ports..." -ForegroundColor Yellow

# Core dev ports
Stop-ProcessOnPort -Port $script:AutoArt.BackendPort
Stop-ProcessOnPort -Port $script:AutoArt.FrontendPort
Stop-ProcessOnPort -Port $script:AutoArt.AutoHelperPort

# Forms app port
Stop-ProcessOnPort -Port 5174

# Additional common Vite fallback ports
$additionalPorts = @(5175, 5176, 5177, 5178)
foreach ($port in $additionalPorts) {
    Stop-ProcessOnPort -Port $port
}

Write-Host ""
Write-Host "[*] Checking for orphaned node processes..." -ForegroundColor Yellow

$projectDir = $script:AutoArt.ProjectDir

# Find node processes related to this project
[array]$nodeProcesses = @(Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine) {
            # Match processes running from our project directories
            $isAutoArt = $cmdLine -match [regex]::Escape($projectDir) -or
                $cmdLine -match "tsx" -and $cmdLine -match "backend" -or
                $cmdLine -match "vite" -and ($cmdLine -match "frontend" -or $cmdLine -match "forms") -or
                $cmdLine -match "autoart"
            return $isAutoArt
        }
        return $false
    }
    catch {
        return $false
    }
})

if ($null -ne $nodeProcesses -and $nodeProcesses.Count -gt 0) {
    Write-Host "[i] Found $($nodeProcesses.Count) AutoArt node process(es)" -ForegroundColor Yellow
    foreach ($proc in $nodeProcesses) {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
            $shortCmd = if ($cmdLine.Length -gt 80) { $cmdLine.Substring(0, 80) + "..." } else { $cmdLine }
            Write-Host "    PID $($proc.Id): $shortCmd" -ForegroundColor Gray
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Write-Host "[OK] Stopped process $($proc.Id)" -ForegroundColor Green
        }
        catch {
            Write-Host "[!] Could not stop process $($proc.Id): $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}
else {
    Write-Host "[i] No orphaned node processes found" -ForegroundColor Gray
}

# Also check for python/uvicorn processes (AutoHelper)
Write-Host ""
Write-Host "[*] Checking for orphaned Python processes..." -ForegroundColor Yellow

[array]$pythonProcesses = @(Get-Process -Name "python", "python3", "uvicorn" -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine) {
            return $cmdLine -match [regex]::Escape($projectDir) -or $cmdLine -match "autohelper"
        }
        return $false
    }
    catch {
        return $false
    }
})

if ($null -ne $pythonProcesses -and $pythonProcesses.Count -gt 0) {
    Write-Host "[i] Found $($pythonProcesses.Count) AutoArt Python process(es)" -ForegroundColor Yellow
    foreach ($proc in $pythonProcesses) {
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Write-Host "[OK] Stopped Python process $($proc.Id)" -ForegroundColor Green
        }
        catch {
            Write-Host "[!] Could not stop Python process $($proc.Id): $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}
else {
    Write-Host "[i] No orphaned Python processes found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "  All AutoArt processes stopped" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
