param()

$ErrorActionPreference = "Stop"

$marker = 'SKILL_CODE_REVIEW_HOOK'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceHook = Join-Path $scriptDir 'pre-push'

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "[code-review] not inside a git work tree"
}

$hookFile = (git rev-parse --git-path hooks/pre-push).Trim()
if ([string]::IsNullOrWhiteSpace($hookFile)) {
    Write-Error "[code-review] failed to resolve hook path"
}

$hookDir = Split-Path -Parent $hookFile
if (-not (Test-Path $hookDir)) {
    New-Item -ItemType Directory -Path $hookDir -Force | Out-Null
}

if (-not (Test-Path $sourceHook)) {
    Write-Error "[code-review] source hook not found: $sourceHook"
}

if (Test-Path $hookFile) {
    $existingIsManaged = Select-String -Path $hookFile -Pattern $marker -Quiet -ErrorAction SilentlyContinue
    if ($existingIsManaged) {
        Write-Host "[code-review] existing claude-skills hook found, upgrading"
    } else {
        $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $backup = "$hookFile.backup-$timestamp"
        Move-Item -Path $hookFile -Destination $backup
        Write-Host "[code-review] backed up third-party hook to: $backup"
    }
}

Copy-Item -Path $sourceHook -Destination $hookFile -Force

Write-Host "[code-review] installed hook to: $hookFile"
Write-Host "[code-review] next steps:"
Write-Host "  - test: git push"
Write-Host "  - bypass once: `$env:SKIP_REVIEW='1'; git push"
Write-Host "  - bypass once: git push --no-verify"
Write-Host "  - strict mode: `$env:REVIEW_STRICT='1'; git push"
Write-Host "  - uninstall: bash $scriptDir/uninstall.sh"
