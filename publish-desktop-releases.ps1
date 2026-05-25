param(
    # Avoid shadowing PowerShell's automatic $PROFILE; -Profile remains supported as an alias.
    [Alias("Profile")]
    [ValidateSet("full", "web-only", "all")]
    [string]$ReleaseProfile = "all",
    [switch]$Build,
    [switch]$SkipVersionedBundle,
    [string]$ProjectRoot = "",
    [string]$SourceDistFull = "",
    [string]$SourceDistWebOnly = "",
    [string]$ManagedAppDist = "",
    [string]$InstalledRelease = "F:\AI\stream-sub-translator-desktop-release",
    [string]$CleanRelease = "F:\AI\stream-sub-translator-desktop-release-clean"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSCommandPath
}
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path

$FullExeName = "Stream Subtitle Translator.exe"
$WebOnlyExeName = "Stream Subtitle Translator Only Web.exe"

if ([string]::IsNullOrWhiteSpace($SourceDistFull)) {
    $SourceDistFull = Join-Path $ProjectRoot "dist\bootstrap-launcher"
}
if ([string]::IsNullOrWhiteSpace($SourceDistWebOnly)) {
    $SourceDistWebOnly = Join-Path $ProjectRoot "dist\bootstrap-launcher-web-only"
}
if ([string]::IsNullOrWhiteSpace($ManagedAppDist)) {
    $ManagedAppDist = Join-Path $ProjectRoot "dist\Stream Subtitle Translator"
}

function Get-ProjectVersion {
    param([Parameter(Mandatory = $true)][string]$Root)
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        $python = "python"
    }
    $value = & $python -c "from backend.versioning import PROJECT_VERSION; print(PROJECT_VERSION)" 2>$null
    if (-not $value) {
        throw "Failed to read PROJECT_VERSION from backend/versioning.py"
    }
    return [string]$value.Trim()
}

function Invoke-BuildProfile {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$BuildProfile
    )
    if ($BuildProfile -eq "full" -or $BuildProfile -eq "all") {
        $buildScript = Join-Path $Root "build-bootstrap-launcher.bat"
        if (-not (Test-Path -LiteralPath $buildScript)) {
            throw "Missing build script: $buildScript"
        }
        Write-Host "[build] build-bootstrap-launcher.bat"
        & cmd.exe /c "`"$buildScript`""
        if ($LASTEXITCODE -ne 0) {
            throw "build-bootstrap-launcher.bat failed with exit code $LASTEXITCODE"
        }
    }
    if ($BuildProfile -eq "web-only" -or $BuildProfile -eq "all") {
        $buildScript = Join-Path $Root "build-bootstrap-launcher-web-only.bat"
        if (-not (Test-Path -LiteralPath $buildScript)) {
            throw "Missing build script: $buildScript"
        }
        Write-Host "[build] build-bootstrap-launcher-web-only.bat"
        & cmd.exe /c "`"$buildScript`""
        if ($LASTEXITCODE -ne 0) {
            throw "build-bootstrap-launcher-web-only.bat failed with exit code $LASTEXITCODE"
        }
    }
}

function Copy-ReleaseExe {
    param(
        [Parameter(Mandatory = $true)][string]$SourceExe,
        [Parameter(Mandatory = $true)][string]$DestinationFolder
    )
    if (-not (Test-Path -LiteralPath $SourceExe)) {
        throw "Missing build output: $SourceExe"
    }
    New-Item -ItemType Directory -Force -Path $DestinationFolder | Out-Null
    Copy-Item -LiteralPath $SourceExe -Destination (Join-Path $DestinationFolder (Split-Path -Leaf $SourceExe)) -Force
}

function Publish-ProfileToReleaseFolders {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("full", "web-only", "all")][string]$PublishProfile,
        [Parameter(Mandatory = $true)][string]$SourceFull,
        [Parameter(Mandatory = $true)][string]$SourceWebOnly,
        [Parameter(Mandatory = $true)][string]$Installed,
        [Parameter(Mandatory = $true)][string]$Clean
    )

    $targets = @($Installed, $Clean)
    foreach ($target in $targets) {
        if ($PublishProfile -eq "full" -or $PublishProfile -eq "all") {
            Copy-ReleaseExe -SourceExe (Join-Path $SourceFull $FullExeName) -DestinationFolder $target
        }
        if ($PublishProfile -eq "web-only" -or $PublishProfile -eq "all") {
            Copy-ReleaseExe -SourceExe (Join-Path $SourceWebOnly $WebOnlyExeName) -DestinationFolder $target
        }
    }
}

function Publish-VersionedBundle {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Version,
        [Parameter(Mandatory = $true)][string]$SourceFull,
        [Parameter(Mandatory = $true)][string]$SourceWebOnly,
        [Parameter(Mandatory = $true)][string]$ManagedDist
    )

    $bundleRoot = Join-Path $Root ("dist\desktop-releases\v{0}" -f $Version)
    $oneFileFull = Join-Path $bundleRoot "01-bootstrap-onefile"
    $oneFileWeb = Join-Path $bundleRoot "01-bootstrap-web-only-onefile"
    $managedFolder = Join-Path $bundleRoot "02-managed-app-onefolder"
    $installersBoth = Join-Path $bundleRoot "03-installers-both"

    foreach ($dir in @($oneFileFull, $oneFileWeb, $managedFolder, $installersBoth)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }

    Copy-ReleaseExe -SourceExe (Join-Path $SourceFull $FullExeName) -DestinationFolder $oneFileFull
    Copy-ReleaseExe -SourceExe (Join-Path $SourceWebOnly $WebOnlyExeName) -DestinationFolder $oneFileWeb
    Copy-ReleaseExe -SourceExe (Join-Path $SourceFull $FullExeName) -DestinationFolder $installersBoth
    Copy-ReleaseExe -SourceExe (Join-Path $SourceWebOnly $WebOnlyExeName) -DestinationFolder $installersBoth

    $managedExe = Join-Path $ManagedDist "Stream Subtitle Translator.exe"
    if (-not (Test-Path -LiteralPath $managedDist)) {
        throw "Missing managed app folder: $managedDist"
    }
    if (Test-Path -LiteralPath $managedExe) {
        Get-ChildItem -LiteralPath $ManagedDist -Force | ForEach-Object {
            $destination = Join-Path $managedFolder $_.Name
            if ($_.PSIsContainer) {
                Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
            } else {
                Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
            }
        }
    } else {
        Write-Warning "Managed app exe not found at $managedExe - skipping 02-managed-app-onefolder mirror."
    }

    $readme = @(
        "Stream Subtitle Translator desktop release bundle v$Version",
        "",
        "01-bootstrap-onefile/          -> $FullExeName (profile splash)",
        "01-bootstrap-web-only-onefile/ -> $WebOnlyExeName (Web Speech quick start)",
        "02-managed-app-onefolder/      -> embedded managed runtime (PyInstaller one-folder)",
        "03-installers-both/            -> both bootstrap launchers for distribution",
        ""
    ) -join [Environment]::NewLine
    Set-Content -LiteralPath (Join-Path $bundleRoot "README.txt") -Value $readme -Encoding UTF8

    Write-Host "[done] Versioned bundle: $bundleRoot"
}

if ($Build) {
    Invoke-BuildProfile -Root $ProjectRoot -BuildProfile $ReleaseProfile
}

Publish-ProfileToReleaseFolders `
    -PublishProfile $ReleaseProfile `
    -SourceFull $SourceDistFull `
    -SourceWebOnly $SourceDistWebOnly `
    -Installed $InstalledRelease `
    -Clean $CleanRelease

Write-Host "[done] Installed desktop release updated: $InstalledRelease"
Write-Host "[done] Clean desktop release refreshed: $CleanRelease"

if (-not $SkipVersionedBundle) {
    $version = Get-ProjectVersion -Root $ProjectRoot
    Publish-VersionedBundle `
        -Root $ProjectRoot `
        -Version $version `
        -SourceFull $SourceDistFull `
        -SourceWebOnly $SourceDistWebOnly `
        -ManagedDist $ManagedAppDist
}
