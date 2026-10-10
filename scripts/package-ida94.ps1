[CmdletBinding()]
param(
    [string]$Binary = (Join-Path $PSScriptRoot '../build-ida94/Release/Ponce64.dll'),
    [string]$VcpkgDirectory = (Join-Path $PSScriptRoot '../.deps/vcpkg'),
    [string]$Version = ''
)
$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dist = Join-Path $repository 'dist'
if ($Version -and $Version -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') { throw 'Version must be a simple tag name.' }
$package = Join-Path $dist 'Ponce_ida94'
New-Item -ItemType Directory -Path (Join-Path $package 'licenses') -Force | Out-Null
Copy-Item -LiteralPath $Binary -Destination (Join-Path $package 'Ponce64.dll')
Copy-Item -LiteralPath (Join-Path $repository 'LICENSE'),(Join-Path $repository 'README.md') -Destination $package
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'dependencies.json') -Destination $package
Copy-Item -LiteralPath (Join-Path $repository 'validation') -Destination $package -Recurse -Force
foreach ($library in @('triton', 'capstone', 'z3')) {
    $copyright = Join-Path $VcpkgDirectory "installed/x64-windows-static-release/share/$library/copyright"
    Copy-Item -LiteralPath $copyright -Destination (Join-Path $package "licenses/$library.txt")
}
$digest = (Get-FileHash -LiteralPath (Join-Path $package 'Ponce64.dll') -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $package 'SHA256SUMS') -Value "$digest  Ponce64.dll" -Encoding ascii
$install = @'
Ponce for IDA Pro 9.4 on Windows x64

1. Close IDA before replacing an existing Ponce installation.
2. Copy Ponce64.dll from this folder to <IDA Pro 9.4>\plugins\Ponce64.dll.
3. Open IDA and a supported binary. Configure symbolic mode under Edit > Ponce.
4. Start IDA's debugger, pause, symbolize input memory or a register, and trace
   a conditional branch before using Ponce's solver actions.

IDA 9.4 uses one Ponce64.dll for both 32-bit and 64-bit input programs.
Triton, Capstone and Z3 are linked statically; no extra dependency DLLs are needed.
This build targets IDA 9.4. It is not an IDA 7.x/8.x plugin build.

The validation folder records the tested binary's hash and actual x86/x64
symbolic execution results. Snapshot restore, solution injection and ARM
runtime are not covered by those tests.

Source, build instructions and runnable tests: https://github.com/4xura/Ponce
'@
Set-Content -LiteralPath (Join-Path $package 'INSTALL.txt') -Value $install -Encoding utf8
Copy-Item -LiteralPath (Join-Path $package 'Ponce64.dll') -Destination (Join-Path $dist 'Ponce64.dll')
if ($Version) { $archiveName = "ponce-$Version-win.zip" } else { $archiveName = 'Ponce-IDA-9.4-Windows.zip' }
$archive = Join-Path $dist $archiveName
Compress-Archive -LiteralPath $package -DestinationPath $archive -Force
$archiveDigest = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $dist 'SHA256SUMS.txt') -Value @("$digest  Ponce64.dll", "$archiveDigest  $archiveName") -Encoding ascii
Write-Output $archive
