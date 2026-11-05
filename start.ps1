$ErrorActionPreference = 'Stop'
$studioRoot = $PSScriptRoot
$studioPort = 8765
$studioUrl = "http://127.0.0.1:$studioPort"
$studioRuntime = Join-Path $studioRoot 'runtime'
New-Item -ItemType Directory -Path $studioRuntime -Force | Out-Null
try {
    $studioExisting = Invoke-RestMethod "$studioUrl/api/state" -TimeoutSec 2
    if ($studioExisting.device.vid -eq '1CBE') {
        Start-Process $studioUrl
        exit 0
    }
} catch {}
$studioVenvPython = Join-Path $studioRoot '.venv\Scripts\python.exe'
$studioPython = if (Test-Path -LiteralPath $studioVenvPython -PathType Leaf) { $studioVenvPython } else { (Get-Command python -ErrorAction Stop).Source }
$studioProcess = Start-Process -FilePath $studioPython -ArgumentList @('-X','utf8',('"' + (Join-Path $studioRoot 'server.py') + '"')) -WorkingDirectory $studioRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $studioRuntime 'stdout.log') -RedirectStandardError (Join-Path $studioRuntime 'stderr.log')
for ($studioTry = 0; $studioTry -lt 30; $studioTry++) {
    Start-Sleep -Milliseconds 300
    try {
        $studioReady = Invoke-RestMethod "$studioUrl/api/state" -TimeoutSec 1
        if ($studioReady.device.vid -eq '1CBE') {
            Start-Process $studioUrl
            Write-Output "TURZX Studio ready: $studioUrl (PID $($studioProcess.Id))"
            exit 0
        }
    } catch {}
    if ($studioProcess.HasExited) { break }
}
throw "TURZX Studio did not start. See runtime/stderr.log."
