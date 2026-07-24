$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot 'backend'
$frontendRoot = Join-Path $repoRoot 'frontend'
$backendPython = Join-Path $backendRoot '.venv\Scripts\python.exe'
$backendRunPy = Join-Path $backendRoot 'run.py'

try {
    Push-Location $frontendRoot
    npm run build | Out-Null
}
finally {
    Pop-Location
}

$commandLineNeedle = ($backendRunPy -replace '/', '\\')
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq 'python.exe' -and
        $_.CommandLine -and
        $_.CommandLine.Contains($commandLineNeedle)
    } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Process -FilePath $backendPython -ArgumentList $backendRunPy -WorkingDirectory $backendRoot -WindowStyle Hidden
