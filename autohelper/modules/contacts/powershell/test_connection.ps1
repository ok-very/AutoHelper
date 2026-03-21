<#
.SYNOPSIS
    Test Exchange Online connectivity (non-blocking).

    Uses -Device flag so it works from subprocesses. If no cached token
    exists, Connect-ExchangeOnline will prompt for device code which would
    block — we wrap it in a PowerShell job with a 10s timeout to detect
    that case and return "not connected" instead of hanging.

.PARAMETER AuthJson
    JSON string with auth credentials (email + password, or app_id + cert_thumbprint + organization).
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$AuthJson
)

$ErrorActionPreference = "Stop"

$result = @{
    connected = $false
    message   = ""
}

try {
    $auth = $AuthJson | ConvertFrom-Json

    if (-not (Get-Module -ListAvailable -Name ExchangeOnlineManagement)) {
        $result.message = "ExchangeOnlineManagement module not installed. Run: Install-Module ExchangeOnlineManagement -Force"
        $result | ConvertTo-Json -Compress
        exit 1
    }

    Import-Module ExchangeOnlineManagement -ErrorAction Stop

    $connectParams = @{ ShowBanner = $false }

    if ($auth.app_id -and $auth.cert_thumbprint -and $auth.organization) {
        # Certificate-based auth (service mode) — fast, no prompt
        $connectParams.AppId = $auth.app_id
        $connectParams.CertificateThumbprint = $auth.cert_thumbprint
        $connectParams.Organization = $auth.organization
    }
    elseif ($auth.email) {
        # Device code flow — will use cached token if available, otherwise prompts
        $connectParams.UserPrincipalName = $auth.email
        $connectParams.Device = $true
    }
    else {
        $result.message = "No credentials configured. Add email in Settings > Exchange Connection."
        $result | ConvertTo-Json -Compress
        exit 1
    }

    # Run connection in a job with timeout so device-code prompt doesn't block
    $job = Start-Job -ScriptBlock {
        param($params)
        Import-Module ExchangeOnlineManagement -ErrorAction Stop
        Connect-ExchangeOnline @params
        $org = Get-OrganizationConfig -ErrorAction Stop
        Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
        return $org.DisplayName
    } -ArgumentList @(,$connectParams)

    $completed = Wait-Job $job -Timeout 10
    if (-not $completed) {
        # Timed out — likely waiting for device code auth (no cached session)
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
        $result.message = "Not connected (no cached session — use Connect first)"
        $result | ConvertTo-Json -Compress
        exit 0
    }

    $jobResult = Receive-Job $job -ErrorAction Stop
    Remove-Job $job -Force -ErrorAction SilentlyContinue

    $result.connected = $true
    $result.message = "Connected to $jobResult"
}
catch {
    $result.message = "Connection failed: $($_.Exception.Message)"
}

$result | ConvertTo-Json -Compress
