param(
    [switch]$ProbeViolation
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$allowed = @{
    'ai-ex-domain' = @()
    'ai-ex-protocol' = @('ai-ex-domain')
    'ai-ex-event-bus' = @('ai-ex-domain', 'ai-ex-protocol')
    'ai-ex-bilibili' = @('ai-ex-domain', 'ai-ex-event-bus')
    'ai-ex-plugin' = @('ai-ex-domain')
    'ai-ex-simulator' = @('ai-ex-domain', 'ai-ex-event-bus', 'ai-ex-memory')
    'ai-ex-config' = @('ai-ex-domain')
    'ai-ex-text' = @('ai-ex-domain')
    'ai-ex-core' = @('ai-ex-domain', 'ai-ex-text', 'ai-ex-protocol')
    'ai-ex-duplex' = @('ai-ex-domain')
    'ai-ex-asr' = @('ai-ex-domain', 'ai-ex-duplex')
    'ai-ex-capture' = @('ai-ex-domain', 'ai-ex-duplex')
    'ai-ex-audio' = @('ai-ex-core', 'ai-ex-domain', 'ai-ex-text')
    'ai-ex-memory' = @('ai-ex-core', 'ai-ex-domain')
    'ai-ex-deepseek' = @('ai-ex-core', 'ai-ex-domain')
    'ai-ex-ollama' = @('ai-ex-core', 'ai-ex-domain')
    'ai-ex-koboldcpp' = @('ai-ex-core', 'ai-ex-domain')
    'ai-ex-tts' = @('ai-ex-domain')
    'ai-ex-vts' = @('ai-ex-core', 'ai-ex-domain')
    'ai-ex-observability' = @('ai-ex-core', 'ai-ex-domain')
    'ai-ex-safety' = @('ai-ex-domain')
    'ai-ex-automation' = @('ai-ex-domain', 'ai-ex-safety')
    'ai-ex-audit' = @('ai-ex-automation', 'ai-ex-domain', 'ai-ex-safety')
    'ai-ex-vision' = @('ai-ex-domain')
    'ai-ex-control' = @('ai-ex-domain', 'ai-ex-observability')
    'ai-ex-ui-model' = @('ai-ex-domain', 'ai-ex-observability')
    'ai-ex-migrate' = @('ai-ex-config', 'ai-ex-domain')
    'ai-ex-service' = @(
        'ai-ex-asr', 'ai-ex-audit', 'ai-ex-audio', 'ai-ex-capture',
        'ai-ex-config', 'ai-ex-control', 'ai-ex-core', 'ai-ex-domain', 'ai-ex-event-bus',
        'ai-ex-deepseek',
        'ai-ex-duplex', 'ai-ex-koboldcpp', 'ai-ex-memory', 'ai-ex-observability',
        'ai-ex-ollama',
        'ai-ex-safety', 'ai-ex-tts', 'ai-ex-vision', 'ai-ex-vts'
    )
}

$metadata = cargo metadata --no-deps --locked --offline --format-version 1
if ($LASTEXITCODE -ne 0)
{
    throw 'cargo metadata failed'
}
$metadata = $metadata | ConvertFrom-Json
$workspaceIds = [Collections.Generic.HashSet[string]]::new(
    [string[]]$metadata.workspace_members
)
$workspaceNames = [Collections.Generic.HashSet[string]]::new()
foreach ($package in $metadata.packages)
{
    if ($workspaceIds.Contains([string]$package.id))
    {
        [void]$workspaceNames.Add([string]$package.name)
    }
}

$violations = [Collections.Generic.List[object]]::new()
if ($ProbeViolation)
{
    $violations.Add([pscustomobject]@{
        package = 'ai-ex-domain'
        dependency = 'ai-ex-service'
    })
}
foreach ($package in $metadata.packages)
{
    if (!$workspaceIds.Contains([string]$package.id))
    {
        continue
    }
    if (!$allowed.ContainsKey([string]$package.name))
    {
        $violations.Add([pscustomobject]@{
            package = $package.name
            dependency = '<missing architecture policy>'
        })
        continue
    }
    foreach ($dependency in $package.dependencies)
    {
        if ($workspaceNames.Contains([string]$dependency.name) -and
            $dependency.name -notin $allowed[$package.name])
        {
            $violations.Add([pscustomobject]@{
                package = $package.name
                dependency = $dependency.name
            })
        }
    }
}

if ($violations.Count -gt 0)
{
    [pscustomobject]@{
        status = 'failed'
        violations = $violations
    } | ConvertTo-Json -Depth 4
    exit 1
}

[pscustomobject]@{
    status = 'passed'
    checked_packages = $workspaceIds.Count
} | ConvertTo-Json -Compress
