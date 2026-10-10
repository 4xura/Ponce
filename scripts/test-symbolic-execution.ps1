[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$IdaDirectory)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ida = Join-Path $IdaDirectory 'ida.exe'
if (-not (Test-Path -LiteralPath $ida)) { throw 'IdaDirectory must contain ida.exe.' }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$visualStudio = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $visualStudio) { throw 'Visual Studio C++ tools are required to assemble the owned probes.' }
$toolset = Get-ChildItem -LiteralPath (Join-Path $visualStudio 'VC/Tools/MSVC') -Directory | Sort-Object Name -Descending | Select-Object -First 1
$linker = Join-Path $toolset.FullName 'bin/Hostx64/x64/link.exe'
$runRoot = Join-Path $repository ('build-ida94/symbolic-run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $runRoot 'ida-user') -Force | Out-Null
$previousIdaUser = $env:IDAUSR
try {
    $env:IDAUSR = Join-Path $runRoot 'ida-user'
    foreach ($bits in @(64, 32)) {
        $work = Join-Path $runRoot "x$bits"
        New-Item -ItemType Directory -Path $work | Out-Null
        $object = Join-Path $work 'probe.obj'
        $binary = Join-Path $work 'probe.exe'
        if ($bits -eq 64) {
            $assembler = Join-Path $toolset.FullName 'bin/Hostx64/x64/ml64.exe'
            $source = Join-Path $repository 'tests/symbolic-addition.asm'
            $machine = 'X64'
        } else {
            $assembler = Join-Path $toolset.FullName 'bin/Hostx64/x86/ml.exe'
            $source = Join-Path $repository 'tests/symbolic-addition-x86.asm'
            $machine = 'X86'
        }
        & $assembler /nologo /Zi /c "/I$(Join-Path $repository 'tests')" "/Fo$object" $source
        if ($LASTEXITCODE -ne 0) { throw "$bits-bit probe assembly failed." }
        $linkArgs = @('/NOLOGO', '/ENTRY:ponce_entry', '/SUBSYSTEM:CONSOLE', "/MACHINE:$machine", '/NODEFAULTLIB', '/DEBUG', '/DYNAMICBASE:NO', '/FIXED', '/EXPORT:ponce_entry', '/EXPORT:ponce_branch', '/EXPORT:ponce_true', '/EXPORT:ponce_false', '/EXPORT:ponce_input,DATA', "/OUT:$binary", "/PDB:$(Join-Path $work 'probe.pdb')", $object)
        if ($bits -eq 32) { $linkArgs += '/SAFESEH:NO' }
        & $linker @linkArgs
        if ($LASTEXITCODE -ne 0) { throw "$bits-bit probe linking failed." }
        $result = Join-Path $work 'result.json'
        $testScript = Join-Path $PSScriptRoot 'test-symbolic-execution.py'
        $arguments = @('-A', ('-L"' + (Join-Path $work 'ida.log') + '"'), ('-S"' + '\"' + $testScript + '\" \"' + $result + '\""'), ('"' + $binary + '"'))
        $process = Start-Process -FilePath $ida -ArgumentList $arguments -WorkingDirectory $work -WindowStyle Hidden -PassThru
        if (-not $process.WaitForExit(50000)) { throw "Probe IDA process $($process.Id) has not finished; result directory: $work" }
        if ($process.ExitCode -ne 0) { throw "$bits-bit symbolic test failed. Inspect $work" }
        $readout = Get-Content -LiteralPath $result -Raw | ConvertFrom-Json
        if (-not $readout.passed -or $readout.solver_value -ne 35) { throw "Invalid $bits-bit solver result: $result" }
        Write-Output "$bits-bit symbolic execution passed: input + 7 == 42 -> input = 35. Evidence: $result"
    }
} finally {
    $env:IDAUSR = $previousIdaUser
}
