param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [string]$PythonVersion = "3.11.9"
)

$ErrorActionPreference = "Stop"

$runtimeDir = Join-Path $ProjectRoot ".python"
$runtimePython = Join-Path $runtimeDir "python.exe"
$bootstrapDir = Join-Path $ProjectRoot ".bootstrap"
$packageName = "python.$PythonVersion.nupkg"
$packagePath = Join-Path $bootstrapDir $packageName
$packageUrl = "https://api.nuget.org/v3-flatcontainer/python/$PythonVersion/$packageName"
$extractDir = Join-Path $bootstrapDir "python-$PythonVersion-package"
$extractToolsDir = Join-Path $extractDir "tools"

function Write-Step([string]$message) {
    Write-Host "[python-bootstrap] $message"
}

function Test-UsablePython([string]$pythonPath) {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        return $false
    }

    try {
        $result = & $pythonPath -c "import sys; print(1 if sys.version_info >= (3, 11) else 0)" 2>$null
        return ($LASTEXITCODE -eq 0 -and $result -match "1")
    } catch {
        return $false
    }
}

function Get-PythonCandidates([string]$searchRoot) {
    if (-not (Test-Path -LiteralPath $searchRoot)) {
        return @()
    }

    $candidates = Get-ChildItem -LiteralPath $searchRoot -Filter "python.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "\\Scripts\\" } |
        Sort-Object { $_.FullName.Length }

    return @($candidates | ForEach-Object { $_.FullName })
}

function Get-PythonBootstrapDiagnostics([string]$searchRoot, [string]$preferredPath) {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Expected interpreter: $preferredPath")
    $lines.Add("Project runtime dir: $searchRoot")
    $lines.Add("python.exe exists at expected path: $(Test-Path -LiteralPath $preferredPath)")

    if (Test-Path -LiteralPath $preferredPath) {
        try {
            $versionOutput = & $preferredPath --version 2>&1 | Select-Object -First 1
            $lines.Add("Expected interpreter version probe: $versionOutput")
        } catch {
            $lines.Add("Expected interpreter version probe failed: $($_.Exception.Message)")
        }
    }

    $candidates = @(Get-PythonCandidates $searchRoot)
    if ($candidates.Count -eq 0) {
        $lines.Add("No python.exe candidates were found under the project runtime directory.")
    } else {
        $lines.Add("Detected python.exe candidates:")
        foreach ($candidate in $candidates) {
            $lines.Add("  - $candidate")
        }
    }

    return ($lines -join [Environment]::NewLine)
}

function Reset-Directory([string]$path) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}

function Expand-NupkgArchive([string]$archivePath, [string]$destinationPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($archivePath, $destinationPath)
}

function Copy-PythonRuntime([string]$sourceDir, [string]$targetDir) {
    Reset-Directory $targetDir
    $null = robocopy $sourceDir $targetDir /E /NFL /NDL /NJH /NJS /NP
    $robocopyExit = $LASTEXITCODE
    if ($robocopyExit -ge 8) {
        throw "robocopy failed while copying the project-local Python runtime from $sourceDir to $targetDir (exit code $robocopyExit)."
    }
}

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

if (Test-UsablePython $runtimePython) {
    Write-Step "Project-local Python already present: $runtimePython"
    exit 0
}

New-Item -ItemType Directory -Path $bootstrapDir -Force | Out-Null

if (-not (Test-Path -LiteralPath $packagePath)) {
    Write-Step "Downloading official CPython $PythonVersion package..."
    Write-Step "Source: $packageUrl"
    try {
        Invoke-WebRequest -Uri $packageUrl -OutFile $packagePath -UseBasicParsing
    } catch {
        if (Test-Path -LiteralPath $packagePath) {
            Remove-Item -LiteralPath $packagePath -Force -ErrorAction SilentlyContinue
        }
        Write-Error "Failed to download Python package from $packageUrl`n$($_.Exception.Message)"
        exit 1
    }
} else {
    Write-Step "Reusing downloaded package: $packagePath"
}

if (-not (Test-Path -LiteralPath $packagePath)) {
    Write-Error "Python package was expected at $packagePath but is missing."
    exit 1
}

Write-Step "Extracting CPython package into $extractDir ..."
try {
    Reset-Directory $extractDir
    Expand-NupkgArchive -archivePath $packagePath -destinationPath $extractDir
} catch {
    Write-Error "Failed to extract Python package $packagePath`n$($_.Exception.Message)"
    exit 1
}

if (-not (Test-UsablePython (Join-Path $extractToolsDir "python.exe"))) {
    $diagnostics = Get-PythonBootstrapDiagnostics -searchRoot $extractDir -preferredPath (Join-Path $extractToolsDir "python.exe")
    Write-Error "The extracted Python package does not contain a usable interpreter.`n$diagnostics"
    exit 1
}

Write-Step "Provisioning CPython into $runtimeDir ..."
try {
    Copy-PythonRuntime -sourceDir $extractToolsDir -targetDir $runtimeDir
} catch {
    Write-Error $_.Exception.Message
    exit 1
}

if (-not (Test-UsablePython $runtimePython)) {
    $diagnostics = Get-PythonBootstrapDiagnostics -searchRoot $runtimeDir -preferredPath $runtimePython
    Write-Error "Project-local Python provisioning completed, but the interpreter is still missing or unusable.`n$diagnostics"
    exit 1
}

Write-Step "Project-local Python is ready: $runtimePython"
exit 0
