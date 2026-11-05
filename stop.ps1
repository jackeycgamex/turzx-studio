$ErrorActionPreference = 'Stop'
try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/control' -Method Post -ContentType 'application/json' -Body '{"action":"shutdown"}' -TimeoutSec 12 | Out-Null
    Write-Output 'Shutdown requested. TURZX Studio is releasing its renderer and USB handle; the screen retains its last frame.'
} catch {
    Write-Output 'The local service is not responding. No unrelated process was stopped.'
}
