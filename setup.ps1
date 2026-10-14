$ErrorActionPreference = 'Stop'
$venvPath = Join-Path $PSScriptRoot '.venv'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCommand) {
        throw 'uv가 설치되어 있지 않습니다. https://docs.astral.sh/uv/getting-started/installation/ 에서 uv를 설치한 뒤 setup.ps1을 다시 실행하세요.'
    }

    Write-Host 'Python 3.11을 준비합니다...'
    & $uvCommand.Source python install 3.11
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 설치에 실패했습니다.' }

    Write-Host '이 실험 폴더에 가상환경을 만듭니다...'
    & $uvCommand.Source venv --python 3.11 $venvPath
    if ($LASTEXITCODE -ne 0) { throw '가상환경 생성에 실패했습니다.' }
}

& $pythonPath -c 'import psychopy'
if ($LASTEXITCODE -eq 0) {
    Write-Host "실험용 PsychoPy가 이미 설치되어 있습니다: $pythonPath"
    exit 0
}

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    Write-Host '실험 실행에 필요한 PsychoPy만 설치합니다. 처음에는 시간이 걸릴 수 있습니다...'
    & $uvCommand.Source pip install --python $pythonPath psychopy
} else {
    Write-Host '기존 Python 환경에 실험용 PsychoPy만 설치합니다. 처음에는 시간이 걸릴 수 있습니다...'
    & $pythonPath -m pip install psychopy
}
if ($LASTEXITCODE -ne 0) { throw 'PsychoPy 설치에 실패했습니다.' }

Write-Host '준비 완료. 실행은 .\run.ps1 --sound-check 또는 .\run.ps1 입니다.'
