param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ManageArgs
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$tempPath = Join-Path $projectRoot "luu_tru\tam"
New-Item -ItemType Directory -Path $tempPath -Force | Out-Null

$env:PYTHONDONTWRITEBYTECODE = "1"
$env:TEMP = $tempPath
$env:TMP = $tempPath

Push-Location $projectRoot
try {
    & py -3.12 manage.py @ManageArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
