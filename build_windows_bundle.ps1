$ErrorActionPreference = "Stop"

$script:TaskLog = [System.Collections.Generic.List[object]]::new()

function Add-TaskLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [ValidateSet("E", "W", "I")]
        [string]$Status,

        [string]$Message = ""
    )

    $script:TaskLog.Add([pscustomobject]@{
            Task = $Name
            Status = $Status
            Message = $Message
        })
}

function Show-TaskSummary {
    Write-Host "`n=== Task summary ===" -ForegroundColor Cyan
    foreach ($task in $script:TaskLog) {
        $color = switch ($task.Status) {
            "E" { "Red" }
            "W" { "Yellow" }
            "I" { "Green" }
            default { "White" }
        }

        $message = if ([string]::IsNullOrWhiteSpace($task.Message)) { "-" } else { $task.Message }
        Write-Host ("[{0}] {1} - {2}" -f $task.Status, $task.Task, $message) -ForegroundColor $color
    }
    Write-Host "===================" -ForegroundColor Cyan
}

function Show-RootCause {
    param(
        [string]$Step,
        [System.Exception]$Exception
    )

    Write-Host "" -ForegroundColor Red
    Write-Host "[ERROR] $Step" -ForegroundColor Red
    if ($Exception) {
        Write-Host "Root cause: $($Exception.Message)" -ForegroundColor Red
        if ($Exception.InnerException) {
            Write-Host "Inner exception: $($Exception.InnerException.Message)" -ForegroundColor DarkRed
        }
        Write-Host $Exception.ToString() -ForegroundColor DarkGray
    }
    Write-Host "" -ForegroundColor Red
}

function Read-RestartChoice {
    $choice = Read-Host "Restart (y/N)"
    return $choice -match '^(y|yes)$'
}

function Remove-BuildRoot {
    param(
        [string]$PathToClean
    )

    if (Test-Path $PathToClean) {
        Remove-Item -Path $PathToClean -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$sourceRoot = $PSScriptRoot
$versionFile = Join-Path $sourceRoot "VERSION"
$version = if (Test-Path $versionFile) { (Get-Content -Path $versionFile -Raw).Trim() } else { "0.1.0" }
$buildRoot = "C:\Dev\Homebank-New"
$bundleDir = Join-Path $buildRoot "dist\HomeBankConverterGUI"
$distRoot = Join-Path $buildRoot "dist"
$workDir = Join-Path $buildRoot "build"
$releaseRoot = Join-Path $sourceRoot "releases"
$releaseDir = Join-Path $releaseRoot "HomeBankConverterGUI-v$version"
$archivePath = Join-Path $releaseRoot "HomeBankConverterGUI-v$version.zip"
$buildSucceeded = $false

try {
    Add-TaskLog -Name "Prepare build root" -Status "I" -Message "Starting bundle preparation at $buildRoot"
    if (Test-Path $buildRoot) {
        Remove-BuildRoot -PathToClean $buildRoot
    }

    New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null

    foreach ($item in Get-ChildItem -Path $sourceRoot -Force) {
        if ($item.Name -in @(".git", ".venv", "__pycache__", "dist", "build")) {
            continue
        }

        $destinationPath = Join-Path $buildRoot $item.Name
        Copy-Item -Path $item.FullName -Destination $destinationPath -Recurse -Force
    }
    Add-TaskLog -Name "Copy project files" -Status "I" -Message "Copied source tree into build workspace"

    $iconIco = Join-Path $buildRoot "12218940.ico"
    if (-not (Test-Path $iconIco)) {
        Add-TaskLog -Name "Validate icon" -Status "E" -Message "Application icon not found: $iconIco"
        throw "Application icon not found: $iconIco"
    }
    Add-TaskLog -Name "Validate icon" -Status "I" -Message "Found application icon"

    $python = "python"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $python = "py"
    }

    $venvPython = Join-Path $buildRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        $venvArgs = @("-m", "venv", (Join-Path $buildRoot ".venv"))
        & $python @venvArgs
        Add-TaskLog -Name "Create venv" -Status "I" -Message "Created virtual environment"
    }
    else {
        Add-TaskLog -Name "Create venv" -Status "W" -Message "Reused existing virtual environment"
    }

    $pythonExe = if (Test-Path $venvPython) { $venvPython } else { $python }
    & $pythonExe -m pip install --upgrade pip
    Add-TaskLog -Name "Upgrade pip" -Status "I" -Message "Python packaging tools updated"

    & $pythonExe -m pip install -r (Join-Path $buildRoot "requirements.txt")
    Add-TaskLog -Name "Install project dependencies" -Status "I" -Message "Requirements installed for the bundle build"

    & $pythonExe -m pip install pyinstaller
    Add-TaskLog -Name "Install PyInstaller" -Status "I" -Message "PyInstaller installed successfully"

    Push-Location $buildRoot
    try {
        $rulesSource = Join-Path $buildRoot "scripts\payment_rules.json"
        $buildArgs = @(
            "-m", "PyInstaller",
            "--noconfirm",
            "--onedir",
            "--windowed",
            "--name", "HomeBankConverterGUI",
            "--icon", $iconIco,
            "--add-data", "$rulesSource;scripts",
            "--collect-submodules", "scripts",
            "--distpath", $distRoot,
            "--workpath", $workDir,
            "--specpath", (Join-Path $buildRoot "_spec"),
            "scripts/gui_launcher.py"
        )

        $noClean = $env:HBCONV_NOCLEAN -eq "1"
        if (-not $noClean) {
            $buildArgs += "--clean"
        }

        $savedEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $buildOutput = & $pythonExe @buildArgs 2>&1
        $pyiExitCode  = $LASTEXITCODE
        $ErrorActionPreference = $savedEAP

        if ($pyiExitCode -ne 0) {
            $message = ($buildOutput | Out-String).Trim()
            Add-TaskLog -Name "PyInstaller build" -Status "E" -Message "PyInstaller exited with code $pyiExitCode. $message"
            throw "PyInstaller exited with code $pyiExitCode. $message"
        }

        Add-TaskLog -Name "PyInstaller build" -Status "I" -Message "Bundle built successfully"
    }
    finally {
        Pop-Location
    }

    $exePath = Get-ChildItem -Path $distRoot -Recurse -Filter "HomeBankConverterGUI.exe" | Select-Object -First 1
    if (-not $exePath) {
        Add-TaskLog -Name "Validate bundle" -Status "E" -Message "Bundle validation failed: HomeBankConverterGUI.exe was not created under $distRoot"
        throw "Build validation failed: HomeBankConverterGUI.exe was not created under $distRoot"
    }
    Add-TaskLog -Name "Validate bundle" -Status "I" -Message "Executable found at $($exePath.FullName)"

    $projectTargetDir = Join-Path $sourceRoot "dist\HomeBankConverterGUI"
    if (-not (Test-Path $projectTargetDir)) {
        New-Item -ItemType Directory -Path $projectTargetDir -Force | Out-Null
    }

    $copiedExe = Join-Path $projectTargetDir "HomeBankConverterGUI.exe"
    Copy-Item -Path $exePath.FullName -Destination $copiedExe -Force
    Add-TaskLog -Name "Copy project bundle" -Status "I" -Message "Executable copied to $copiedExe"

    if (Test-Path $releaseRoot) {
        Remove-Item -Path $releaseRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null

    if (Test-Path $releaseDir) {
        Remove-Item -Path $releaseDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

    Copy-Item -Path (Join-Path $projectTargetDir '*') -Destination $releaseDir -Recurse -Force

    $releaseManifest = @"
HomeBank Converter Release
Version: $version
Built: $(Get-Date -Format o)
Bundle: HomeBankConverterGUI.exe

This package contains the Windows desktop bundle and release notes.
"@
    Set-Content -Path (Join-Path $releaseDir "RELEASE_NOTES.txt") -Value $releaseManifest -Encoding UTF8

    if (Test-Path $archivePath) {
        Remove-Item -Path $archivePath -Force -ErrorAction SilentlyContinue
    }

    Compress-Archive -Path (Join-Path $releaseDir '*') -DestinationPath $archivePath -Force
    Add-TaskLog -Name "Create release bundle" -Status "I" -Message "Release archive created at $archivePath"

    $buildSucceeded = $true
    Write-Host "Build succeeded." -ForegroundColor Green
    Write-Host "Bundle ready at: $bundleDir" -ForegroundColor Green
    Write-Host "Executable: $($exePath.FullName)" -ForegroundColor Green
    Write-Host "Copied to project target: $copiedExe" -ForegroundColor Green
    Write-Host "Release archive: $archivePath" -ForegroundColor Green
}
catch {
    $buildSucceeded = $false
    Show-RootCause -Step "Windows bundle build failed" -Exception $_.Exception
}
finally {
    Show-TaskSummary

    if ($buildSucceeded) {
        $restartBuild = Read-RestartChoice
        if ($restartBuild) {
            & $PSCommandPath
        }
        else {
            Remove-BuildRoot -PathToClean $buildRoot
            Write-Host "Cleaned $buildRoot" -ForegroundColor DarkYellow
        }
    }
    else {
        $restartBuild = Read-RestartChoice
        if ($restartBuild) {
            & $PSCommandPath
        }
        else {
            Remove-BuildRoot -PathToClean $buildRoot
            Write-Host "Cleaned $buildRoot" -ForegroundColor DarkYellow
        }
    }
}
