[CmdletBinding()]
param(
    [Parameter()]
    [string] $ScanPath = (Join-Path $PSScriptRoot '..\crates'),

    [Parameter()]
    [switch] $ProbeViolation
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$resolvedPath = (Resolve-Path -LiteralPath $ScanPath).Path
$files = Get-ChildItem -LiteralPath $resolvedPath -Recurse -File -Filter '*.rs'
$violations = [System.Collections.Generic.List[object]]::new()
$sameLineBrace = '^\s*(?:if|else(?:\s+if)?|for|while|loop|match)\b[^\{]*\{\s*$'

foreach ($file in $files)
{
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $file.FullName -Encoding UTF8)
    {
        $lineNumber++
        if ($line -match $sameLineBrace)
        {
            $violations.Add([pscustomobject]@{
                file = $file.FullName
                line = $lineNumber
                text = $line.Trim()
            })
        }
    }
}

if ($ProbeViolation)
{
    $violations.Add([pscustomobject]@{
        file = '<probe>'
        line = 1
        text = 'if ready {'
    })
}

if ($violations.Count -gt 0)
{
    [pscustomobject]@{
        status = 'failed'
        violation_count = $violations.Count
        violations = $violations
    } | ConvertTo-Json -Depth 4
    exit 1
}

[pscustomobject]@{
    status = 'passed'
    checked_files = $files.Count
} | ConvertTo-Json -Compress
