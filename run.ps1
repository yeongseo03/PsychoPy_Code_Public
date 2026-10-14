$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "PsychoPy 환경이 아직 없습니다. 먼저 이 폴더에서 .\setup.ps1 을 실행하세요."
}
& $pythonPath (Join-Path $PSScriptRoot 'experiment.py') @args
