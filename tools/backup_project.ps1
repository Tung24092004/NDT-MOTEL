param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_-]+$')]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string[]]$Source,

    [switch]$WhatIf
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$archiveRoot = Join-Path $projectRoot "luu_tru\ban_sao_luu"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$destination = Join-Path $archiveRoot ("{0}_{1}" -f $Name, $timestamp)

$resolvedSources = foreach ($item in $Source) {
    $candidate = Join-Path $projectRoot $item
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw "Khong tim thay nguon backup: $item"
    }

    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $resolved.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar)) {
        throw "Nguon nam ngoai du an: $resolved"
    }
    if ($resolved.StartsWith((Join-Path $projectRoot "luu_tru") + [IO.Path]::DirectorySeparatorChar)) {
        throw "Khong dung luu_tru lam nguon backup: $resolved"
    }
    $resolved
}

Write-Output "Thu muc dich: $destination"
Write-Output "Nguon:"
$resolvedSources | ForEach-Object { Write-Output "- $_" }

if ($WhatIf) {
    Write-Output "Kiem tra thanh cong; chua tao backup."
    exit 0
}

if (Test-Path -LiteralPath $destination) {
    throw "Thu muc dich da ton tai: $destination"
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($resolved in $resolvedSources) {
    Copy-Item -LiteralPath $resolved -Destination $destination -Recurse
}

Write-Output "Da tao backup: $destination"
