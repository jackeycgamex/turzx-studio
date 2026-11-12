param([switch]$Disable)
$ErrorActionPreference = 'Stop'
$studioRoot = $PSScriptRoot
$studioRunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$studioRunName = 'TURZXStudio'
if ($Disable) {
    Remove-ItemProperty -LiteralPath $studioRunKey -Name $studioRunName -ErrorAction SilentlyContinue
    Write-Output 'TURZX Studio login startup disabled.'
    exit 0
}
$studioVenvPythonw = Join-Path $studioRoot '.venv\Scripts\pythonw.exe'
$studioPythonw = if (Test-Path -LiteralPath $studioVenvPythonw -PathType Leaf) {
    $studioVenvPythonw
} else {
    Join-Path (Split-Path (Get-Command python -ErrorAction Stop).Source) 'pythonw.exe'
}
if (-not (Test-Path -LiteralPath $studioPythonw -PathType Leaf)) { throw 'pythonw.exe is required for windowless startup.' }
$studioEntry = Join-Path $studioRoot 'background_start.pyw'
if (-not (Test-Path -LiteralPath $studioEntry -PathType Leaf)) { throw 'background_start.pyw is missing.' }
$studioCommand = '"{0}" -X utf8 "{1}"' -f $studioPythonw,$studioEntry
New-Item -Path $studioRunKey -Force | Out-Null
New-ItemProperty -LiteralPath $studioRunKey -Name $studioRunName -Value $studioCommand -PropertyType String -Force | Out-Null
Write-Output 'TURZX Studio will start silently when this Windows user signs in.'
Write-Output $studioCommand
