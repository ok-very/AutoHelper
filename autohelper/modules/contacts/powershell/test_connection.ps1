<#
.SYNOPSIS
    Test Exchange Online connectivity.

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
        # Certificate-based auth (service mode)
        $connectParams.AppId = $auth.app_id
        $connectParams.CertificateThumbprint = $auth.cert_thumbprint
        $connectParams.Organization = $auth.organization
    }
    elseif ($auth.email -and $auth.password) {
        # Credential-based auth (email + password)
        $secPass = ConvertTo-SecureString $auth.password -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential($auth.email, $secPass)
        $connectParams.Credential = $cred
        $connectParams.UserPrincipalName = $auth.email
    }
    elseif ($auth.email) {
        # UPN-only (will trigger interactive prompt if needed)
        $connectParams.UserPrincipalName = $auth.email
    }
    else {
        $result.message = "No credentials configured. Add email and password in Settings > Exchange Connection."
        $result | ConvertTo-Json -Compress
        exit 1
    }

    Connect-ExchangeOnline @connectParams

    # Quick verification - list organization config
    $orgConfig = Get-OrganizationConfig -ErrorAction Stop
    $result.connected = $true
    $result.message = "Connected to $($orgConfig.DisplayName)"

    Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
}
catch {
    $result.message = "Connection failed: $($_.Exception.Message)"
}

$result | ConvertTo-Json -Compress
