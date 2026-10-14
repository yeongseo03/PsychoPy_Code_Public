$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'PsychoPy 환경이 없습니다. 먼저 이 폴더에서 .\setup.ps1 을 실행하세요.'
}
throw '이 실험 패키지에는 PsychoPy Builder 앱을 설치하지 않습니다. 실험 실행은 .\run.ps1 을 사용하세요.'
