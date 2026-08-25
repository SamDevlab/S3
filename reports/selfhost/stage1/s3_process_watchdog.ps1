param(
    [string]$StatePath = (Join-Path $PSScriptRoot "AUTONOMOUS_PROCESS_STATE.json"),
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\.."))
)

$ErrorActionPreference = "Stop"

function Get-State {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return $null
    }
    return Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
}

function Test-ProcessAlive([int]$ProcessId) {
    if ($ProcessId -le 0) {
        return $false
    }
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

while ($true) {
    $state = Get-State
    if ($null -eq $state) {
        exit 0
    }

    if ($state.status -notin @("RUNNING", "ABORTED")) {
        exit 0
    }

    $controllerAlive = Test-ProcessAlive ([int]$state.controller_pid)
    $trackedAlive = $false
    foreach ($tracked in @($state.tracked_processes)) {
        if (Test-ProcessAlive ([int]$tracked.pid)) {
            $trackedAlive = $true
            break
        }
    }

    if ($controllerAlive -or $trackedAlive -or $state.normal_shutdown_started) {
        Start-Sleep -Seconds 5
        continue
    }

    if ([int]$state.controller_pid -le 0) {
        Start-Sleep -Seconds 5
        continue
    }

    $state.status = "EMERGENCY_FINALIZING"
    $state.campaign_process_tree_terminated_unexpectedly = $true
    $state.emergency_shutdown_requested = $true
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatePath -Encoding UTF8

    $desktop = [Environment]::GetFolderPath("Desktop")
    git -C $RepositoryRoot status --short | Set-Content (Join-Path $desktop "S3_EMERGENCY_GIT_STATUS.txt")
    git -C $RepositoryRoot diff | Set-Content (Join-Path $desktop "S3_EMERGENCY_WORKTREE.patch")
    git -C $RepositoryRoot diff --cached | Set-Content (Join-Path $desktop "S3_EMERGENCY_INDEX.patch")
    @(
        "DATE=$((Get-Date).ToString('o'))"
        "REASON=CAMPAIGN_PROCESS_TREE_TERMINATED"
        "HEAD=$((git -C $RepositoryRoot rev-parse HEAD).Trim())"
        "BRANCH=$((git -C $RepositoryRoot branch --show-current).Trim())"
        "STATUS=$($state.status)"
        "WATCHDOG_TRIGGERED=YES"
    ) | Set-Content (Join-Path $desktop "S3_EMERGENCY_HANDOFF.txt")
    shutdown.exe /s /t 15 /c "S3 Codex process ended before normal completion. Local work state was preserved."
    exit 0
}
