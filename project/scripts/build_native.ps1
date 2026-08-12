param(
    [string]$DependencyRoot = "$env:LOCALAPPDATA\google-autocomplete-vcpkg",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable"
    }
}

if ($DependencyRoot -match "[^\x00-\x7F]") {
    throw "DependencyRoot must contain ASCII characters only, for example C:\vcpkg-google"
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$vswhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path -LiteralPath $vswhere)) {
    throw "Visual Studio Installer was not found."
}

$visualStudio = & $vswhere `
    -latest `
    -products * `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath
if (-not $visualStudio) {
    throw "Install the Desktop development with C++ workload first."
}

$vcpkg = Join-Path $visualStudio "VC\vcpkg\vcpkg.exe"
$cmake = Join-Path $visualStudio `
    "Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
if (-not (Test-Path -LiteralPath $vcpkg)) {
    throw "vcpkg was not found: $vcpkg"
}
if (-not (Test-Path -LiteralPath $cmake)) {
    throw "CMake was not found: $cmake"
}

New-Item -ItemType Directory -Path $DependencyRoot -Force | Out-Null

if (-not $SkipDependencyInstall) {
    Invoke-Checked -Executable $vcpkg -Arguments @(
        "install",
        "--triplet", "x64-windows",
        "--x-manifest-root=$projectRoot",
        "--x-install-root=$DependencyRoot"
    )
}

$prefixPath = Join-Path $DependencyRoot "x64-windows"
if (-not (Test-Path -LiteralPath $prefixPath)) {
    throw "Protobuf dependencies were not found: $prefixPath"
}

$buildDirectory = Join-Path $projectRoot "native\build-protobuf"
Invoke-Checked -Executable $cmake -Arguments @(
    "-S", (Join-Path $projectRoot "native"),
    "-B", $buildDirectory,
    "-A", "x64",
    "-DCMAKE_PREFIX_PATH=$prefixPath"
)
Invoke-Checked -Executable $cmake -Arguments @(
    "--build", $buildDirectory,
    "--config", "Release"
)
Invoke-Checked -Executable $cmake -Arguments @(
    "--build", $buildDirectory,
    "--config", "Release",
    "--target", "RUN_TESTS"
)

Write-Host "Native build and tests completed successfully."
