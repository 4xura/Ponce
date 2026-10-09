[CmdletBinding()]
param(
    [string]$DependencyRoot = (Join-Path $PSScriptRoot '../.deps'),
    [string]$SdkDirectory,
    [string]$VcpkgDirectory,
    [string]$BuildDirectory = (Join-Path $PSScriptRoot '../build-ida94'),
    [string]$IdaDirectory,
    [int]$Parallel = 8
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$DependencyRoot = [IO.Path]::GetFullPath($DependencyRoot)
$lock = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'dependencies.json') -Raw | ConvertFrom-Json

function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}

function Initialize-Checkout([string]$Directory, [string]$Url, [string]$Revision) {
    if (-not (Test-Path -LiteralPath (Join-Path $Directory '.git'))) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
        Invoke-Checked git @('init', $Directory)
        Invoke-Checked git @('-C', $Directory, 'remote', 'add', 'origin', $Url)
        Invoke-Checked git @('-C', $Directory, 'fetch', '--depth', '1', 'origin', $Revision)
        Invoke-Checked git @('-C', $Directory, 'checkout', '--detach', 'FETCH_HEAD')
    }
    $head = & git -C $Directory rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $head.Trim() -ne $Revision) {
        throw "Dependency at $Directory does not match pinned revision $Revision"
    }
}

if (-not $SdkDirectory) { $SdkDirectory = Join-Path $DependencyRoot 'ida-sdk94' }
if (-not $VcpkgDirectory) { $VcpkgDirectory = Join-Path $DependencyRoot 'vcpkg' }
Initialize-Checkout $SdkDirectory 'https://github.com/HexRaysSA/ida-sdk.git' $lock.sdkCommit
Initialize-Checkout $VcpkgDirectory 'https://github.com/microsoft/vcpkg.git' $lock.vcpkgCommit

$env:VCPKG_DISABLE_METRICS = '1'
$env:VCPKG_MAX_CONCURRENCY = [string]$Parallel
$vcpkg = Join-Path $VcpkgDirectory 'vcpkg.exe'
if (-not (Test-Path -LiteralPath $vcpkg)) {
    Invoke-Checked (Join-Path $VcpkgDirectory 'bootstrap-vcpkg.bat') @('-disableMetrics')
}
$triplet = 'x64-windows-static-release'
$overlay = Join-Path $repository 'cmake/triplets'
Invoke-Checked $vcpkg @('install', 'triton', '--triplet', $triplet, "--overlay-triplets=$overlay")

$cmakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
if ($cmakeCommand) {
    $cmake = $cmakeCommand.Source
} else {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $visualStudio = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    $cmake = Join-Path $visualStudio 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
}
if (-not (Test-Path -LiteralPath $cmake)) { throw 'CMake and Visual Studio C++ build tools are required.' }
$build = [IO.Path]::GetFullPath($BuildDirectory)
Invoke-Checked $cmake @('-S', $repository, '-B', $build, '-G', 'Visual Studio 17 2022', '-A', 'x64',
    "-DIDASDK_ROOT_DIR=$SdkDirectory", "-DCMAKE_TOOLCHAIN_FILE=$VcpkgDirectory/scripts/buildsystems/vcpkg.cmake",
    "-DVCPKG_TARGET_TRIPLET=$triplet",
    '-DBUILD_EXAMPLES=OFF', '-DBUILD_HEXRAYS_SUPPORT=ON')
Invoke-Checked $cmake @('--build', $build, '--config', 'Release', '--target', 'Ponce64', '--parallel', [string]$Parallel)

$binary = Join-Path $build 'Release/Ponce64.dll'
Write-Output "Built $binary"
if ($IdaDirectory) {
    if (-not (Test-Path -LiteralPath (Join-Path $IdaDirectory 'ida.exe'))) { throw 'IdaDirectory must contain ida.exe.' }
    Copy-Item -LiteralPath $binary -Destination (Join-Path $IdaDirectory 'plugins/Ponce64.dll')
    Write-Output 'Installed Ponce64.dll. Restart IDA to load it.'
}
