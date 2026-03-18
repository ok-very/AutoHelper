<#
.SYNOPSIS
    Sync contacts to Exchange Online via ExchangeOnlineManagement module.

.DESCRIPTION
    Reads a JSON input file containing auth credentials and contact operations
    (create, update, delete). Connects to Exchange Online, executes operations,
    and outputs JSON results to stdout.

.PARAMETER InputFile
    Path to JSON file with auth and operations.

.NOTES
    Requires: ExchangeOnlineManagement module
    Install: Install-Module ExchangeOnlineManagement -Force
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$InputFile
)

$ErrorActionPreference = "Stop"

# Result accumulator
$result = @{
    created = 0
    updated = 0
    deleted = 0
    errors  = @()
}

try {
    # Read input
    $input = Get-Content -Path $InputFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $auth = $input.auth

    # Import Exchange Online module
    if (-not (Get-Module -ListAvailable -Name ExchangeOnlineManagement)) {
        $result.errors += "ExchangeOnlineManagement module not installed"
        $result | ConvertTo-Json -Compress
        exit 1
    }

    Import-Module ExchangeOnlineManagement -ErrorAction Stop

    # Connect to Exchange Online
    $connectParams = @{}

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
        # UPN-only
        $connectParams.UserPrincipalName = $auth.email
    }
    else {
        $result.errors += "No credentials configured. Add email and password in Settings > Exchange Connection."
        $result | ConvertTo-Json -Compress
        exit 1
    }

    Connect-ExchangeOnline @connectParams

    # Process creates
    foreach ($contact in $input.create) {
        try {
            $newParams = @{
                Name                 = $contact.Identity
                ExternalEmailAddress = $contact.ExternalEmailAddress
                FirstName            = $contact.FirstName
                LastName             = $contact.LastName
            }

            # Remove empty values
            $newParams = $newParams.GetEnumerator() | Where-Object { $_.Value } |
                ForEach-Object -Begin { $h = @{} } -Process { $h[$_.Key] = $_.Value } -End { $h }

            New-MailContact @newParams -ErrorAction Stop

            # Set additional properties via Set-Contact
            $setParams = @{
                Identity = $contact.ExternalEmailAddress
            }

            if ($contact.Company)          { $setParams.Company          = $contact.Company }
            if ($contact.Title)            { $setParams.Title            = $contact.Title }
            if ($contact.Phone)            { $setParams.Phone            = $contact.Phone }
            if ($contact.MobilePhone)      { $setParams.MobilePhone      = $contact.MobilePhone }
            if ($contact.StreetAddress)    { $setParams.StreetAddress    = $contact.StreetAddress }
            if ($contact.City)             { $setParams.City             = $contact.City }
            if ($contact.StateOrProvince)  { $setParams.StateOrProvince  = $contact.StateOrProvince }
            if ($contact.PostalCode)       { $setParams.PostalCode       = $contact.PostalCode }
            if ($contact.CountryOrRegion)  { $setParams.CountryOrRegion  = $contact.CountryOrRegion }

            if ($setParams.Count -gt 1) {
                Set-Contact @setParams -ErrorAction Stop
            }

            # Set custom attribute via Set-MailContact
            if ($contact.CustomAttribute1) {
                Set-MailContact -Identity $contact.ExternalEmailAddress `
                    -CustomAttribute1 $contact.CustomAttribute1 -ErrorAction Stop
            }

            $result.created++
        }
        catch {
            $result.errors += "Create $($contact.ExternalEmailAddress): $($_.Exception.Message)"
        }
    }

    # Process updates
    foreach ($contact in $input.update) {
        try {
            $setContactParams = @{
                Identity = $contact.ExternalEmailAddress
            }

            if ($contact.DisplayName)      {
                Set-MailContact -Identity $contact.ExternalEmailAddress `
                    -DisplayName $contact.DisplayName -ErrorAction Stop
            }
            if ($contact.Company)          { $setContactParams.Company          = $contact.Company }
            if ($contact.Title)            { $setContactParams.Title            = $contact.Title }
            if ($contact.Phone)            { $setContactParams.Phone            = $contact.Phone }
            if ($contact.MobilePhone)      { $setContactParams.MobilePhone      = $contact.MobilePhone }
            if ($contact.StreetAddress)    { $setContactParams.StreetAddress    = $contact.StreetAddress }
            if ($contact.City)             { $setContactParams.City             = $contact.City }
            if ($contact.StateOrProvince)  { $setContactParams.StateOrProvince  = $contact.StateOrProvince }
            if ($contact.PostalCode)       { $setContactParams.PostalCode       = $contact.PostalCode }
            if ($contact.CountryOrRegion)  { $setContactParams.CountryOrRegion  = $contact.CountryOrRegion }

            Set-Contact @setContactParams -ErrorAction Stop

            if ($contact.CustomAttribute1) {
                Set-MailContact -Identity $contact.ExternalEmailAddress `
                    -CustomAttribute1 $contact.CustomAttribute1 -ErrorAction Stop
            }

            $result.updated++
        }
        catch {
            $result.errors += "Update $($contact.ExternalEmailAddress): $($_.Exception.Message)"
        }
    }

    # Process deletes
    foreach ($identity in $input.delete) {
        try {
            Remove-MailContact -Identity $identity -Confirm:$false -ErrorAction Stop
            $result.deleted++
        }
        catch {
            $result.errors += "Delete ${identity}: $($_.Exception.Message)"
        }
    }

    # Disconnect
    Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
}
catch {
    $result.errors += "Fatal: $($_.Exception.Message)"
    $result | ConvertTo-Json -Compress
    exit 1
}

# Output JSON result
$result | ConvertTo-Json -Compress
