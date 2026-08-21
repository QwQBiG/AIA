[CmdletBinding()]
param(
    [string]$Path = "config/control.token",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$parent = Split-Path -Parent $Path
if ($parent -and -not (Test-Path -LiteralPath $parent))
{
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
if ((Test-Path -LiteralPath $Path) -and -not $Force)
{
    throw "Token already exists at $Path. Use -Force only when rotation is intentional."
}
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try
{
    $rng.GetBytes($bytes)
}
finally
{
    $rng.Dispose()
}
$token = [Convert]::ToBase64String($bytes)
$fullPath = [System.IO.Path]::GetFullPath($Path)
[System.IO.File]::WriteAllText($fullPath, $token + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Output "Created control token: $Path"

