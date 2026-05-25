param(
    [string]$SourceDist = "F:\AI\stream-sub-translator\dist\bootstrap-launcher-web-only",
    [string]$InstalledRelease = "F:\AI\stream-sub-translator-desktop-release",
    [string]$CleanRelease = "F:\AI\stream-sub-translator-desktop-release-clean",
    [string]$ExeName = "Stream Subtitle Translator Only Web.exe"
)

$ErrorActionPreference = "Stop"

function Publish-WebOnlyExe {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$TargetExeName
    )

    $sourceExe = Join-Path $Source $TargetExeName
    if (-not (Test-Path -LiteralPath $sourceExe)) {
        throw "Missing Web Speech-only bootstrap build: $sourceExe"
    }

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -LiteralPath $sourceExe -Destination (Join-Path $Destination $TargetExeName) -Force
}

Publish-WebOnlyExe -Source $SourceDist -Destination $InstalledRelease -TargetExeName $ExeName
Publish-WebOnlyExe -Source $SourceDist -Destination $CleanRelease -TargetExeName $ExeName

Write-Host "[done] Web Speech-only desktop exe published: $ExeName"
Write-Host "[done] Installed release folder: $InstalledRelease"
Write-Host "[done] Clean release folder: $CleanRelease"
