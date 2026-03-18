<#
.SYNOPSIS
    Generate a self-signed code-signing certificate for MSIX packaging.

.DESCRIPTION
    Creates a self-signed certificate matching the AppxManifest.xml publisher
    identity (CN=ok-very), exports the PFX (private key) and CER (public key).

    Run this ONCE per signing identity. Store the PFX as a GitHub secret
    (AUTOHELPER_SIGN_PFX, base64-encoded). Commit the .cer to the repo —
    users import it to install sideloaded MSIX packages.

.PARAMETER Password
    Password for the PFX file. Required.

.PARAMETER OutputDir
    Directory for output files. Defaults to current directory.

.EXAMPLE
    .\create_cert.ps1 -Password "YourSecurePassword"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Password,

    [string]$OutputDir = "."
)

$ErrorActionPreference = "Stop"

$subject = "CN=ok-very"
$pfxPath = Join-Path $OutputDir "autohelper-sign.pfx"
$cerPath = Join-Path $OutputDir "autohelper-sign.cer"

# Create self-signed code signing cert (5 year expiry)
$cert = New-SelfSignedCertificate `
    -Type Custom `
    -Subject $subject `
    -KeyUsage DigitalSignature `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3") `
    -NotAfter (Get-Date).AddYears(5)

Write-Host "Certificate created: $($cert.Thumbprint)"

# Export PFX (private key — for CI signing)
$securePassword = ConvertTo-SecureString -String $Password -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePassword | Out-Null
Write-Host "PFX exported: $pfxPath"

# Export CER (public key — for sideloading trust)
Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null
Write-Host "CER exported: $cerPath"

# Base64-encode PFX for GitHub secrets
$pfxBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path $pfxPath)))
$b64Path = Join-Path $OutputDir "autohelper-sign.pfx.b64"
Set-Content -Path $b64Path -Value $pfxBase64 -NoNewline
Write-Host "Base64 PFX: $b64Path"

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Add PFX base64 to GitHub secret: AUTOHELPER_SIGN_PFX"
Write-Host "  2. Add PFX password to GitHub secret: AUTOHELPER_SIGN_PFX_PASSWORD"
Write-Host "  3. Commit autohelper-sign.cer to the repo"
Write-Host "  4. Delete autohelper-sign.pfx and .b64 (do NOT commit these)"

# Cleanup cert from local store
Remove-Item "Cert:\CurrentUser\My\$($cert.Thumbprint)" -ErrorAction SilentlyContinue
