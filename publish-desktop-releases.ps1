param(
    [string]$SourceDist = "F:\AI\stream-sub-translator\dist\bootstrap-launcher",
    [string]$InstalledRelease = "F:\AI\stream-sub-translator-desktop-release",
    [string]$CleanRelease = "F:\AI\stream-sub-translator-desktop-release-clean"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath

function Invoke-RobocopyMirror {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy $Source $Destination /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed for '$Source' -> '$Destination' with exit code $LASTEXITCODE"
    }
}

function Remove-IfExists {
    param([Parameter(Mandatory = $true)][string]$PathToRemove)
    if (Test-Path -LiteralPath $PathToRemove) {
        Remove-Item -LiteralPath $PathToRemove -Recurse -Force
    }
}

function Publish-BootstrapRelease {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $Destination -Force | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
    Copy-Item -LiteralPath (Join-Path $Source "Stream Subtitle Translator.exe") -Destination (Join-Path $Destination "Stream Subtitle Translator.exe") -Force
}

Publish-BootstrapRelease -Source $SourceDist -Destination $InstalledRelease
Publish-BootstrapRelease -Source $SourceDist -Destination $CleanRelease

Write-Host "[done] Installed desktop release updated: $InstalledRelease"
Write-Host "[done] Clean desktop release refreshed: $CleanRelease"
