param(
    [string]$DestinationRoot = "desktop remote clean",
    [string]$PackageName = "stream-sub-translator-remote-lite",
    [switch]$Zip
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSCommandPath
$SourceRoot = $ProjectRoot
$ResolvedDestinationRoot = if ([System.IO.Path]::IsPathRooted($DestinationRoot)) {
    $DestinationRoot
} else {
    Join-Path $ProjectRoot $DestinationRoot
}
$DestinationPath = Join-Path $ResolvedDestinationRoot $PackageName
$ZipPath = Join-Path $ResolvedDestinationRoot ($PackageName + ".zip")

if (Test-Path -LiteralPath $DestinationPath) {
    Remove-Item -LiteralPath $DestinationPath -Recurse -Force
}

New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null

$excludeDirectories = @(
    (Join-Path $SourceRoot ".git"),
    (Join-Path $SourceRoot ".venv"),
    (Join-Path $SourceRoot ".python"),
    (Join-Path $SourceRoot ".cache"),
    (Join-Path $SourceRoot ".tmp"),
    (Join-Path $SourceRoot ".bootstrap"),
    (Join-Path $SourceRoot ".codex"),
    (Join-Path $SourceRoot ".vscode"),
    (Join-Path $SourceRoot ".idea"),
    (Join-Path $SourceRoot "build"),
    (Join-Path $SourceRoot "dist"),
    (Join-Path $SourceRoot "desktop"),
    (Join-Path $SourceRoot "logs"),
    (Join-Path $SourceRoot "user-data"),
    (Join-Path $SourceRoot "desktop remote clean"),
    (Join-Path $SourceRoot "SST desktop remote SST"),
    (Join-Path $SourceRoot "backend\\data\\logs"),
    (Join-Path $SourceRoot "backend\\data\\exports"),
    (Join-Path $SourceRoot "backend\\data\\cache"),
    (Join-Path $SourceRoot "backend\\data\\models")
)

$excludeFiles = @(
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.tmp",
    ".env",
    "config.json",
    "install_profile.txt",
    "dictionary_overrides.json",
    "tmp_google_asr_inline_check.js",
    ".tmp-google-asr-inline-check.js"
)

$robocopyArgs = @(
    $SourceRoot,
    $DestinationPath,
    "/E",
    "/R:1",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP",
    "/XD"
) + $excludeDirectories + @(
    "/XF"
) + $excludeFiles

& robocopy @robocopyArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed with exit code $LASTEXITCODE"
}

Get-ChildItem -LiteralPath $DestinationPath -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "__pycache__" } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -LiteralPath $DestinationPath -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
    Remove-Item -Force -ErrorAction SilentlyContinue

$runtimeArtifactDirs = @(
    "backend\\data\\logs",
    "backend\\data\\exports",
    "backend\\data\\cache",
    "backend\\data\\models"
)

foreach ($relativeDir in $runtimeArtifactDirs) {
    $artifactPath = Join-Path $DestinationPath $relativeDir
    if (Test-Path -LiteralPath $artifactPath) {
        Remove-Item -LiteralPath $artifactPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}

New-Item -ItemType Directory -Path (Join-Path $DestinationPath "user-data") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $DestinationPath "user-data\\logs") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $DestinationPath "user-data\\exports") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $DestinationPath "user-data\\cache") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $DestinationPath "user-data\\models") -Force | Out-Null

$packageReadme = @"
# Remote Lite Package

This folder is a lightweight copy of the project for a second PC.

Included:
- source code
- startup scripts
- requirements files

Excluded:
- .venv, .python, caches, logs
- local models and runtime artifacts
- git metadata

First run on second PC:
1. Run `start-remote-worker.bat` for remote worker mode.
2. Run `start-remote-controller.bat` for controller mode.
3. Dependencies are installed automatically on first launch.
"@
Set-Content -LiteralPath (Join-Path $DestinationPath "REMOTE_LITE_README.md") -Value $packageReadme -Encoding UTF8

if ($Zip) {
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $DestinationPath "*") -DestinationPath $ZipPath -Force
    Write-Host "[done] Zip created: $ZipPath"
}

Write-Host "[done] Remote lite package prepared: $DestinationPath"
