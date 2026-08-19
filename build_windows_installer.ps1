$ErrorActionPreference = "Stop"

$sourceRoot = $PSScriptRoot
$versionFile = Join-Path $sourceRoot "VERSION"
$version = if (Test-Path $versionFile) { (Get-Content -Path $versionFile -Raw).Trim() } else { "0.1.0" }

$bundleDir = Join-Path $sourceRoot "dist\HomeBankConverterGUI"
$releaseRoot = Join-Path $sourceRoot "releases"
$releaseDir = Join-Path $releaseRoot "HomeBankConverterGUI-v$version"
$installerSetup = Join-Path $releaseRoot "HomeBankConverterGUI-v$version-setup.exe"
$templatePath = Join-Path $sourceRoot "installer\HomeBankConverterGUI.iss"

if (-not (Test-Path $bundleDir)) {
    Write-Host "Bundle not found at $bundleDir. Building it first..." -ForegroundColor Yellow
    & (Join-Path $sourceRoot "build_windows_bundle.ps1")
    if (-not (Test-Path $bundleDir)) {
        throw "Bundle could not be created at $bundleDir"
    }
}

if (Test-Path $releaseRoot) {
    Remove-Item -Path $releaseRoot -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null

if (Test-Path $releaseDir) {
    Remove-Item -Path $releaseDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

Copy-Item -Path (Join-Path $bundleDir '*') -Destination $releaseDir -Recurse -Force

$issTemplate = Get-Content -Path $templatePath -Raw
$issTemplate = $issTemplate.Replace('"0.1.0"', "`"$version`"")
$issTemplate = $issTemplate.Replace('"C:\\dist\\HomeBankConverterGUI"', "`"$bundleDir`"")
$issTemplate = $issTemplate.Replace('"C:\\releases"', "`"$releaseRoot`"")
$issTemplate = $issTemplate.Replace('"C:\Users\username\OneDrive\\Programming\\Python\\Homebank New\\12218940.ico"', "`"$(Join-Path $sourceRoot "12218940.ico")`"")
$issPath = Join-Path $releaseRoot "HomeBankConverterGUI-v$version.iss"
Set-Content -Path $issPath -Value $issTemplate -Encoding UTF8

$isccCandidates = @(
    (Get-Command iscc -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    "C:\Program Files\Inno Setup 5\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "Inno Setup compiler not found. Creating a zipped export fallback instead." -ForegroundColor Yellow
    $zipArchive = Join-Path $releaseRoot "HomeBankConverterGUI-v$version.zip"
    if (Test-Path $zipArchive) {
        Remove-Item -Path $zipArchive -Force -ErrorAction SilentlyContinue
    }
    Compress-Archive -Path (Join-Path $releaseDir '*') -DestinationPath $zipArchive -Force
    Write-Host "Fallback release zip created at: $zipArchive" -ForegroundColor Green
    return
}

& $iscc $issPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path $installerSetup)) {
    throw "Installer setup was not created at $installerSetup"
}

Write-Host "Installer created successfully: $installerSetup" -ForegroundColor Green
Write-Host "Release directory: $releaseDir" -ForegroundColor Green
