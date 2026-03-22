<#
.SYNOPSIS
    Install Exchange Online Management module for AutoHelper contact sync.

.DESCRIPTION
    Checks for PowerShell 7 (pwsh) and installs ExchangeOnlineManagement
    module if not present. Run this once on initial setup or after OS updates.

.NOTES
    Requires: PowerShell 7+ (pwsh)
    Run as: pwsh -File scripts/setup-exchange.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "AutoHelper Exchange Setup" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan
Write-Host ""

# Check PowerShell version
if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host "[X] PowerShell 7+ required. Current version: $($PSVersionTable.PSVersion)" -ForegroundColor Red
    Write-Host "    Install from: https://aka.ms/powershell-release?tag=stable" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] PowerShell $($PSVersionTable.PSVersion)" -ForegroundColor Green

# Check/install ExchangeOnlineManagement
$module = Get-Module -ListAvailable -Name ExchangeOnlineManagement
if ($module) {
    Write-Host "[OK] ExchangeOnlineManagement $($module.Version) already installed" -ForegroundColor Green
} else {
    Write-Host "[..] Installing ExchangeOnlineManagement..." -ForegroundColor Yellow
    try {
        Install-Module -Name ExchangeOnlineManagement -Force -Scope CurrentUser -AllowClobber -AcceptLicense
        $module = Get-Module -ListAvailable -Name ExchangeOnlineManagement
        Write-Host "[OK] ExchangeOnlineManagement $($module.Version) installed" -ForegroundColor Green
    } catch {
        Write-Host "[X] Failed to install: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Exchange setup complete. Configure credentials in AutoHelper Settings > Contacts." -ForegroundColor Cyan
