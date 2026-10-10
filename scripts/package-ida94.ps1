[CmdletBinding()]
param(
    [string]$Binary = (Join-Path $PSScriptRoot '../build-ida94/Release/Ponce64.dll'),
    [string]$VcpkgDirectory = (Join-Path $PSScriptRoot '../.deps/vcpkg')
)
$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dist = Join-Path $repository 'dist'
$package = Join-Path $dist 'Ponce-IDA-9.4-Windows'
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
$archive = Join-Path $dist 'Ponce-IDA-9.4-Windows.zip'
Compress-Archive -LiteralPath $package -DestinationPath $archive -Force
Write-Output $archive
