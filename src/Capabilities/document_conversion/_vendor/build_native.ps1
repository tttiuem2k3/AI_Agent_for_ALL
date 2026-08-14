param(
    [string]$OutputDirectory = "",
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$vendorRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$capabilityRoot = Split-Path -Parent $vendorRoot
$projectRoot = [IO.Path]::GetFullPath((Join-Path $capabilityRoot "..\..\.."))
$nativeRoot = Join-Path $capabilityRoot "_native"
$bindingRoot = Join-Path $nativeRoot "binding"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Project virtual environment not found: $python. Run 'uv sync --all-extras' first."
}

$cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
if (Test-Path $cargoBin) {
    $env:Path = "$cargoBin;$env:Path"
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Rust cargo >= 1.88 is required. Install Rust with rustup."
}
if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    throw "Rust compiler is unavailable. Run 'rustup default stable'."
}

$rustVersion = & rustc --version
if ($LASTEXITCODE -ne 0) {
    throw "Unable to execute rustc. Repair the active rustup toolchain."
}
$maturinVersion = & $python -m maturin --version 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Maturin >= 1.9,<2 is required in the project .venv."
}

$vswhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $vsRoot = & $vswhere -latest -products * `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
        -property installationPath
    if ($vsRoot) {
        $vcvars = Join-Path $vsRoot "VC\Auxiliary\Build\vcvars64.bat"
        if (Test-Path $vcvars) {
            $command = "call `"$vcvars`" >nul && set"
            foreach ($line in (& cmd.exe /d /s /c $command)) {
                if ($line -match '^([^=]+)=(.*)$') {
                    [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
                }
            }
        }
    }
}

if (-not (Get-Command link.exe -ErrorAction SilentlyContinue)) {
    throw "MSVC linker was not found. Install the Visual Studio C++ x64 toolset."
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $nativeRoot "dist"
}
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

Write-Host "Rust: $rustVersion"
Write-Host "Maturin: $maturinVersion"
Write-Host "Python: $python"
Write-Host "Output: $OutputDirectory"

Push-Location $bindingRoot
try {
    & $python -m maturin build --release --locked `
        --interpreter $python --out $OutputDirectory
    if ($LASTEXITCODE -ne 0) {
        throw "Native wheel build failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$wheel = Get-ChildItem $OutputDirectory -Filter "asoft_document_conversion_native-*.whl" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $wheel) {
    throw "Native build succeeded but the expected wheel was not found."
}
Write-Host "Native wheel: $($wheel.FullName)"

if ($Install) {
    & uv pip install --python $python --link-mode copy --reinstall $wheel.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Native wheel installation failed with exit code $LASTEXITCODE."
    }
    Write-Host "Installed asoft-document-conversion-native into .venv."
}
