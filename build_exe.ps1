$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectDir ".build-venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ReleaseDir = Join-Path $ProjectDir "release"
$BuildDir = Join-Path $ProjectDir "build"
$ExeName = "FDTD无界面一键运行.exe"
$PyInstallerName = "FDTD无界面一键运行"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    python -m venv $VenvDir
}

& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $ProjectDir "requirements-build.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install build dependencies."
}

& $VenvPython (Join-Path $ProjectDir "scripts\generate_icon.py")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate application icon."
}

$IconPath = Join-Path $ProjectDir "assets\fdtd_runner.ico"

& $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --icon $IconPath `
    --add-data "$IconPath;assets" `
    --exclude-module tkinter `
    --exclude-module _tkinter `
    --name $PyInstallerName `
    --version-file (Join-Path $ProjectDir "version_info.txt") `
    --distpath $ReleaseDir `
    --workpath $BuildDir `
    --specpath $BuildDir `
    (Join-Path $ProjectDir "lumerical_runner_zh.py")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$ReleaseSettings = Join-Path $ReleaseDir "settings.json"
if (-not (Test-Path -LiteralPath $ReleaseSettings)) {
    Copy-Item -LiteralPath (Join-Path $ProjectDir "settings.default.json") -Destination $ReleaseSettings
}
Copy-Item -LiteralPath (Join-Path $ProjectDir "README.md") -Destination (Join-Path $ReleaseDir "README.md") -Force
Copy-Item -LiteralPath (Join-Path $ProjectDir "README.md") -Destination (Join-Path $ReleaseDir "README_zh.md") -Force
$ReleaseImages = Join-Path $ReleaseDir "docs\images"
New-Item -ItemType Directory -Path $ReleaseImages -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectDir "docs\images\fdtd-runner-dark.png") -Destination $ReleaseImages -Force
Copy-Item -LiteralPath (Join-Path $ProjectDir "docs\images\fdtd-runner-light.png") -Destination $ReleaseImages -Force
Copy-Item -LiteralPath (Join-Path $ProjectDir "docs\images\fdtd-runner-compact.png") -Destination $ReleaseImages -Force
Copy-Item -LiteralPath (Join-Path $ProjectDir "docs\images\fdtd-runner-icon.png") -Destination $ReleaseImages -Force

$ExePath = Join-Path $ReleaseDir $ExeName
$Hash = (Get-FileHash -LiteralPath $ExePath -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $ReleaseDir "SHA256.txt") -Value "$Hash  $ExeName" -Encoding utf8

foreach ($LegacyExeName in @("Lumerical_FDTD_Runner_ZH.exe", "Lumerical_FDTD_Studio.exe")) {
    $LegacyExePath = Join-Path $ReleaseDir $LegacyExeName
    if ((Test-Path -LiteralPath $LegacyExePath) -and ($LegacyExePath -ne $ExePath)) {
        Remove-Item -LiteralPath $LegacyExePath -Force
    }
}

Write-Host ""
Write-Host "Build complete:"
Write-Host $ExePath
