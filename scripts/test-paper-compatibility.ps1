param(
    [ValidateSet('Prepare','Run')][string]$Mode = 'Prepare',
    [string]$PythonExe = 'python',
    [string]$JavaExe = 'java',
    [switch]$Resume
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$jar = Join-Path $repoRoot 'build\libs\TickSense-0.8.1-compat-test.jar'
$resumeArgs = @()
if ($Resume) { $resumeArgs += '--resume' }
& $PythonExe (Join-Path $PSScriptRoot 'paper_compatibility.py') $Mode --jar $jar --java $JavaExe @resumeArgs
if ($LASTEXITCODE -ne 0) { throw "Compatibility harness exited with code $LASTEXITCODE" }
