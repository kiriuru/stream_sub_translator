param(
    [string]$SourceDist = "F:\AI\stream-sub-translator\dist\Stream Subtitle Translator",
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

function Publish-DesktopCodeLayer {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -LiteralPath (Join-Path $Source "Stream Subtitle Translator.exe") -Destination (Join-Path $Destination "Stream Subtitle Translator.exe") -Force
    Remove-IfExists -PathToRemove (Join-Path $Destination "app-runtime")
    & robocopy (Join-Path $Source "app-runtime") (Join-Path $Destination "app-runtime") /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed for app-runtime '$Source' -> '$Destination' with exit code $LASTEXITCODE"
    }
}

Publish-DesktopCodeLayer -Source $SourceDist -Destination $InstalledRelease
Publish-DesktopCodeLayer -Source $SourceDist -Destination $CleanRelease

Remove-IfExists -PathToRemove (Join-Path $InstalledRelease "backend")

$topLevelTransient = @(".python", ".venv", ".cache", ".tmp")
foreach ($name in $topLevelTransient) {
    Remove-IfExists -PathToRemove (Join-Path $CleanRelease $name)
}

Remove-IfExists -PathToRemove (Join-Path $CleanRelease "user-data")
Remove-IfExists -PathToRemove (Join-Path $CleanRelease "backend")

Write-Host "[done] Installed desktop release updated: $InstalledRelease"
Write-Host "[done] Clean desktop release refreshed: $CleanRelease"
