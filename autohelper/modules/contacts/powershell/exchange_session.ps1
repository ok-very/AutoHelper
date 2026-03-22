<#
.SYNOPSIS
    Persistent Exchange Online session.

    Phase 1: Connect via device code (MSAL prompt goes to stderr).
             Writes "CONNECTED:<OrgName>" to stdout on success.
    Phase 2: Command loop — reads JSON commands from stdin,
             writes JSON responses + sentinel to stdout.

.PARAMETER Email
    UserPrincipalName for device code auth.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Email
)

$ErrorActionPreference = "Stop"
$sentinel = "###CMDEND###"

function Write-Response($obj) {
    [Console]::Out.WriteLine(($obj | ConvertTo-Json -Compress -Depth 5))
    [Console]::Out.WriteLine($sentinel)
    [Console]::Out.Flush()
}

# ── Phase 1: Connect ─────────────────────────────────────────────

try {
    Import-Module ExchangeOnlineManagement -ErrorAction Stop
    Connect-ExchangeOnline -ShowBanner:$false -Device
    $org = Get-OrganizationConfig -ErrorAction Stop
    [Console]::Out.WriteLine("CONNECTED:$($org.DisplayName)")
    [Console]::Out.Flush()
}
catch {
    [Console]::Out.WriteLine("CONNECT_FAILED:$($_.Exception.Message)")
    [Console]::Out.Flush()
    exit 1
}

# ── Phase 2: Command loop ────────────────────────────────────────

while ($true) {
    $line = [Console]::In.ReadLine()
    if ($null -eq $line) { break }
    if ($line.Trim() -eq "") { continue }

    try {
        $cmd = $line | ConvertFrom-Json
    }
    catch {
        Write-Response @{ error = "Invalid JSON" }
        continue
    }

    switch ($cmd.action) {

        "test" {
            try {
                $orgConfig = Get-OrganizationConfig -ErrorAction Stop
                Write-Response @{ connected = $true; message = "Connected to $($orgConfig.DisplayName)" }
            }
            catch {
                Write-Response @{ connected = $false; message = "Test failed: $($_.Exception.Message)" }
            }
        }

        "sync" {
            $resp = @{ created = 0; updated = 0; deleted = 0; errors = @() }

            # ── Creates ──
            foreach ($contact in $cmd.create) {
                try {
                    $newParams = @{
                        Name                 = $contact.Identity
                        ExternalEmailAddress = $contact.ExternalEmailAddress
                        FirstName            = $contact.FirstName
                        LastName             = $contact.LastName
                    }
                    # Remove empty values
                    $cleaned = @{}
                    foreach ($kv in $newParams.GetEnumerator()) {
                        if ($kv.Value) { $cleaned[$kv.Key] = $kv.Value }
                    }

                    New-MailContact @cleaned -ErrorAction Stop | Out-Null

                    # Set additional properties via Set-Contact
                    $setParams = @{ Identity = $contact.ExternalEmailAddress }
                    if ($contact.Company)         { $setParams.Company         = $contact.Company }
                    if ($contact.Title)           { $setParams.Title           = $contact.Title }
                    if ($contact.Phone)           { $setParams.Phone           = $contact.Phone }
                    if ($contact.MobilePhone)     { $setParams.MobilePhone     = $contact.MobilePhone }
                    if ($contact.StreetAddress)   { $setParams.StreetAddress   = $contact.StreetAddress }
                    if ($contact.City)            { $setParams.City            = $contact.City }
                    if ($contact.StateOrProvince) { $setParams.StateOrProvince = $contact.StateOrProvince }
                    if ($contact.PostalCode)      { $setParams.PostalCode      = $contact.PostalCode }
                    if ($contact.CountryOrRegion) { $setParams.CountryOrRegion = $contact.CountryOrRegion }

                    if ($setParams.Count -gt 1) {
                        Set-Contact @setParams -ErrorAction Stop | Out-Null
                    }

                    if ($contact.CustomAttribute1) {
                        Set-MailContact -Identity $contact.ExternalEmailAddress `
                            -CustomAttribute1 $contact.CustomAttribute1 -ErrorAction Stop | Out-Null
                    }

                    $resp.created++
                }
                catch {
                    if ($_.Exception.Message -match "multiple recipients matching identity") {
                        $resp.created++  # already exists in Exchange = success
                    } else {
                        $resp.errors += "Create $($contact.ExternalEmailAddress): $($_.Exception.Message)"
                    }
                }
            }

            # ── Updates ──
            foreach ($contact in $cmd.update) {
                try {
                    if ($contact.DisplayName) {
                        Set-MailContact -Identity $contact.ExternalEmailAddress `
                            -DisplayName $contact.DisplayName -ErrorAction Stop | Out-Null
                    }

                    $setParams = @{ Identity = $contact.ExternalEmailAddress }
                    if ($contact.Company)         { $setParams.Company         = $contact.Company }
                    if ($contact.Title)           { $setParams.Title           = $contact.Title }
                    if ($contact.Phone)           { $setParams.Phone           = $contact.Phone }
                    if ($contact.MobilePhone)     { $setParams.MobilePhone     = $contact.MobilePhone }
                    if ($contact.StreetAddress)   { $setParams.StreetAddress   = $contact.StreetAddress }
                    if ($contact.City)            { $setParams.City            = $contact.City }
                    if ($contact.StateOrProvince) { $setParams.StateOrProvince = $contact.StateOrProvince }
                    if ($contact.PostalCode)      { $setParams.PostalCode      = $contact.PostalCode }
                    if ($contact.CountryOrRegion) { $setParams.CountryOrRegion = $contact.CountryOrRegion }

                    Set-Contact @setParams -ErrorAction Stop

                    if ($contact.CustomAttribute1) {
                        Set-MailContact -Identity $contact.ExternalEmailAddress `
                            -CustomAttribute1 $contact.CustomAttribute1 -ErrorAction Stop | Out-Null
                    }

                    $resp.updated++
                }
                catch {
                    $resp.errors += "Update $($contact.ExternalEmailAddress): $($_.Exception.Message)"
                }
            }

            # ── Deletes ──
            foreach ($identity in $cmd.delete) {
                try {
                    Remove-MailContact -Identity $identity -Confirm:$false -ErrorAction Stop | Out-Null
                    $resp.deleted++
                }
                catch {
                    $resp.errors += "Delete ${identity}: $($_.Exception.Message)"
                }
            }

            Write-Response $resp
        }

        "disconnect" {
            Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
            Write-Response @{ ok = $true; message = "Disconnected" }
            exit 0
        }

        default {
            Write-Response @{ error = "Unknown action: $($cmd.action)" }
        }
    }
}
