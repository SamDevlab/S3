[CmdletBinding()]
param(
    [string]$Root = 'C:\Users\samue\Downloads\S3\S3-PR268-Stage1-Streaming',
    [int]$RefreshSeconds = 3,
    [int]$MaxLogLines = 160,
    [int]$HashIntervalSeconds = 15
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'SilentlyContinue'

$RunDir = Join-Path $Root '.s3-stage1-autonomous-runs'
$JournalPath = Join-Path $RunDir 'runner-journal.log'
$LockPath = Join-Path $Root '.s3-stage1-autonomous.lock'
$DonePath = Join-Path $Root '.s3-stage1-autonomous.done'
$HardStopPath = Join-Path $Root '.s3-stage1-autonomous.hard-stop'
$BatonPath = Join-Path $Root 'reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md'
$CandidatePath = Join-Path $Root 'selfhost/compiler/stage1_semantic_event_spine.s3'
$CanonicalPath = Join-Path $Root 'selfhost/compiler/s3c_stage1.s3'
$ExpectedCanonicalSha = '44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb'

$script:HashCache = @{}
$script:LastRendered = $null

function Get-FileSha256 {
    param([string]$Path)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    }
    catch {
        return 'UNAVAILABLE'
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $sha.Dispose()
    }
}

function Get-CachedFileSnapshot {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject]@{
            Exists = $false
            Sha256 = 'ABSENT'
            Bytes = 0
            LastWrite = 'ABSENT'
            LastWriteTime = $null
        }
    }

    $item = Get-Item -LiteralPath $Path
    $stamp = '{0}|{1}' -f $item.Length, $item.LastWriteTimeUtc.Ticks
    $now = Get-Date
    if ($script:HashCache.ContainsKey($Key)) {
        $cached = $script:HashCache[$Key]
        $cacheAge = ($now - $cached.CalculatedAt).TotalSeconds
        if ($cached.Stamp -eq $stamp -and $cacheAge -lt $HashIntervalSeconds) {
            return $cached.Snapshot
        }
    }

    $snapshot = [pscustomobject]@{
        Exists = $true
        Sha256 = Get-FileSha256 -Path $Path
        Bytes = [int64]$item.Length
        LastWrite = $item.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
        LastWriteTime = $item.LastWriteTime
    }
    $script:HashCache[$Key] = [pscustomobject]@{
        Stamp = $stamp
        CalculatedAt = $now
        Snapshot = $snapshot
    }
    return $snapshot
}

function Get-AgeSeconds {
    param($Item)

    if ($null -eq $Item) { return $null }
    return [math]::Max(0, [math]::Round(((Get-Date) - $Item.LastWriteTime).TotalSeconds, 0))
}

function Format-Age {
    param($Seconds)

    if ($null -eq $Seconds) { return 'unknown' }
    $secondsInt = [int][math]::Max(0, $Seconds)
    if ($secondsInt -lt 60) { return ('{0}s ago' -f $secondsInt) }
    $minutes = [math]::Floor($secondsInt / 60)
    $remainder = $secondsInt % 60
    return ('{0}m {1}s ago' -f $minutes, $remainder)
}

function Format-Uptime {
    param($CreationDate)

    if ($null -eq $CreationDate) { return 'unknown' }
    try {
        $span = (Get-Date) - (Get-Date $CreationDate)
        return ('{0}d {1:00}h {2:00}m {3:00}s' -f $span.Days, $span.Hours, $span.Minutes, $span.Seconds)
    }
    catch {
        return 'unknown'
    }
}

function Get-FieldValue {
    param(
        [string[]]$Lines,
        [string]$Name
    )

    $value = $null
    $prefix = $Name + '='
    foreach ($line in $Lines) {
        if ($line.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
            $value = $line.Substring($prefix.Length).Trim()
        }
    }
    if ($null -eq $value) { return 'UNKNOWN' }
    return $value
}

function Get-FirstAvailableFieldValue {
    param(
        [string[]]$Lines,
        [string[]]$Names
    )

    foreach ($name in $Names) {
        $value = Get-FieldValue -Lines $Lines -Name $name
        if ($value -ne 'UNKNOWN' -and $value.Trim().Length -gt 0) { return $value }
    }
    return 'UNKNOWN'
}

function Get-LastCheckpointName {
    param([string[]]$Lines)

    $line = $Lines | Where-Object { $_ -match '(?i)^## CHECKPOINT' } | Select-Object -Last 1
    if ($null -eq $line) { return 'waiting for checkpoint' }
    return (($line -replace '(?i)^## CHECKPOINT\s+', '') -replace '\s+```.*$', '').Trim()
}

function Convert-ToGateStatus {
    param([string]$Value)

    $upper = if ($null -eq $Value) { 'UNKNOWN' } else { $Value.Trim().ToUpperInvariant() }
    if ($upper -match '^PASS\b') { return 'PASS' }
    if ($upper -match '^FAIL\b') { return 'FAIL' }
    if ($upper -match '^RUN(NING)?\b') { return 'RUN' }
    if ($upper -match 'PARTIAL|PART\b') { return 'PART' }
    if ($upper -match '^(DONE|YES|COMPLETE|COMPLETED)\b') { return 'PASS' }
    if ($upper -match '^RAW_SHA_ASSERTED\b') { return 'PASS' }
    return 'WAIT'
}

function Get-PhaseAControlValue {
    param(
        [string[]]$Lines,
        [string]$Phase
    )

    $explicit = Get-FirstAvailableFieldValue -Lines $Lines -Names @('FOCUSED_V3_MATRIX', 'PHASE_A_CONTROL')
    if ($explicit -ne 'UNKNOWN') { return $explicit }

    $focused = Get-FieldValue -Lines $Lines -Name 'FOCUSED_TESTS'
    $oracle = Get-FieldValue -Lines $Lines -Name 'ORACLE_TESTS'
    if ($Phase -match '(?i)^PHASE_[B-E]_' -and
        $focused -match '(?i)PASS' -and
        $oracle -match '(?i)PASS') {
        return 'PASS'
    }
    return 'UNKNOWN'
}

function Get-CanonicalProbeValue {
    param([string[]]$Lines)

    $explicit = Get-FirstAvailableFieldValue -Lines $Lines -Names @('CANONICAL_PROBE_RUN', 'CANONICAL_PROBE')
    if ($explicit -ne 'UNKNOWN') {
        if ($explicit -match '(?i)^FAIL\b|ERROR') { return 'FAIL' }
        if ($explicit -match '(?i)RAW_SHA_ASSERTED|SINGLE_COMPACT_DEFINITIVE_RESULT_RECOVERED|DONE|COMPLETE') {
            return 'DONE'
        }
        return $explicit
    }
    $loss = Get-FieldValue -Lines $Lines -Name 'FIRST_SEMANTIC_LOSS'
    if ($loss -ne 'UNKNOWN') { return 'DONE' }
    return 'UNKNOWN'
}

function Test-CanonicalFirstLoss {
    param(
        [string[]]$Lines,
        [string]$CheckpointName
    )

    $loss = Get-FieldValue -Lines $Lines -Name 'FIRST_SEMANTIC_LOSS'
    if ($loss -ne 'UNKNOWN' -and $loss.Trim().Length -gt 0) { return $true }
    return $CheckpointName -match '(?i)CANONICAL FIRST LOSS'
}

function Get-CanonicalConformanceValue {
    param(
        [string[]]$Lines,
        [bool]$HasFirstLoss
    )

    if ($HasFirstLoss) { return 'FIRST LOSS' }
    return Get-FirstAvailableFieldValue -Lines $Lines -Names @('CANONICAL_SEMANTIC_CONFORMANCE', 'CANONICAL_CONFORMANCE')
}

function Get-CanonicalLossRepairValue {
    param(
        [string]$Phase,
        [string[]]$Lines
    )

    if ($Phase -match '(?i)CANONICAL_FIRST_LOSS_CONVERGENCE') { return 'RUN' }
    $loss = Get-FieldValue -Lines $Lines -Name 'FIRST_SEMANTIC_LOSS'
    if ($loss -ne 'UNKNOWN') {
        $cycles = Get-FieldValue -Lines $Lines -Name 'CANONICAL_LOSS_CYCLES_COMPLETED'
        if ($cycles -eq 'UNKNOWN' -or $cycles -match '^0\b') { return 'RUN' }
    }
    return Get-FieldValue -Lines $Lines -Name 'CANONICAL_LOSS_CYCLES_COMPLETED'
}

function Get-CanonicalLossDetails {
    param(
        [string[]]$Lines,
        [string]$CheckpointName
    )

    $loss = Get-FieldValue -Lines $Lines -Name 'FIRST_SEMANTIC_LOSS'
    if ($loss -eq 'UNKNOWN' -and $CheckpointName -notmatch '(?i)CANONICAL FIRST LOSS') {
        return $null
    }

    $function = 'UNKNOWN'
    $span = 'UNKNOWN'
    $cause = $loss
    if ($loss -match '(?i)^Canonical\s+(.+?)\s+function,\s*(.*?):\s*(.*)$') {
        $function = $Matches[1].Trim()
        $span = $Matches[2].Trim()
        $cause = $Matches[3].Trim()
    }
    elseif ($loss -eq 'UNKNOWN') {
        $cause = $CheckpointName
    }

    $construct = 'UNKNOWN'
    if ($CheckpointName -match '(?i)LOOP CONTINUATION' -or $loss -match '(?i)\bloop\b') {
        $construct = 'LOOP CONTINUATION'
    }
    return [pscustomobject]@{
        Function = $function
        Span = $span
        Construct = $construct
        Cause = $cause
    }
}

function Get-GateColor {
    param([string]$Status)

    switch ($Status) {
        'PASS' { return 'Green' }
        'FAIL' { return 'Red' }
        'RUN'  { return 'Yellow' }
        'PART' { return 'Yellow' }
        default { return 'DarkYellow' }
    }
}

function Write-ColorLine {
    param(
        [string]$Text,
        [string]$Color = 'Gray'
    )

    Write-Host $Text -ForegroundColor $Color
}

function Write-GateLine {
    param(
        [string]$Label,
        [string]$Value
    )

    $status = Convert-ToGateStatus -Value $Value
    $tag = ('[{0}]' -f $status.PadRight(4))
    Write-Host ('{0,-22} ' -f $Label) -NoNewline
    Write-Host $tag -ForegroundColor (Get-GateColor -Status $status)
}

function Get-ProcessSnapshot {
    $processes = @(Get-CimInstance Win32_Process)
    $lockLines = @()
    if (Test-Path -LiteralPath $LockPath -PathType Leaf) {
        $lockLines = @(Get-Content -LiteralPath $LockPath)
    }

    $lockPid = $null
    $lockPidLine = $lockLines | Where-Object { $_ -like 'PID=*' } | Select-Object -First 1
    if ($null -ne $lockPidLine) {
        try { $lockPid = [int](($lockPidLine -replace '^PID=', '').Trim()) } catch { $lockPid = $null }
    }

    $runnerCandidates = @($processes | Where-Object {
        $_.Name -eq 'pwsh.exe' -and
        $_.CommandLine -match 'run_s3_stage1_autonomous(_v2)?\.ps1' -and
        $_.CommandLine -match [regex]::Escape($Root) -and
        $_.CommandLine -notmatch ' -Command '
    })
    $runner = $null
    if ($null -ne $lockPid) {
        $runner = $processes | Where-Object { $_.ProcessId -eq $lockPid } | Select-Object -First 1
    }
    if ($null -eq $runner) { $runner = $runnerCandidates | Select-Object -First 1 }

    $child = $null
    if ($null -ne $runner) {
        $child = $processes | Where-Object {
            $_.Name -eq 'codex.exe' -and
            $_.ParentProcessId -eq $runner.ProcessId
        } | Select-Object -First 1
    }
    if ($null -eq $child) {
        $child = $processes | Where-Object {
            $_.Name -eq 'codex.exe' -and
            $_.CommandLine -match 'cycle-.*-last\.md' -and
            $_.CommandLine -match [regex]::Escape($Root)
        } | Select-Object -First 1
    }

    $lockAlive = $false
    if ($null -ne $lockPid) {
        $lockAlive = $null -ne ($processes | Where-Object { $_.ProcessId -eq $lockPid } | Select-Object -First 1)
    }
    $lockStatus = 'ABSENT'
    if (Test-Path -LiteralPath $LockPath -PathType Leaf) {
        $lockStatus = if ($lockAlive) { 'VALID' } else { 'STALE/INVALID' }
    }

    return [pscustomobject]@{
        Processes = $processes
        Runner = $runner
        Child = $child
        LockPid = $lockPid
        LockAlive = $lockAlive
        LockStatus = $lockStatus
        RunnerFound = ($null -ne $runner)
        ChildFound = ($null -ne $child)
    }
}

function Get-CurrentLog {
    if (-not (Test-Path -LiteralPath $RunDir -PathType Container)) { return $null }
    return Get-ChildItem -LiteralPath $RunDir -File -Force |
        Where-Object { $_.Name -like 'cycle-*.log' } |
        Sort-Object LastWriteTime |
        Select-Object -Last 1
}

function Get-BoundedLogTail {
    param($LogItem)

    if ($null -eq $LogItem) { return @() }
    return @(Get-Content -LiteralPath $LogItem.FullName -Tail $MaxLogLines)
}

function Get-CompactText {
    param([string]$Text, [int]$MaxLength = 150)

    $compact = ($Text -replace '\s+', ' ').Trim()
    if ($compact.Length -gt $MaxLength) { return $compact.Substring(0, $MaxLength - 3) + '...' }
    return $compact
}

function Get-RecentJournalEvents {
    if (-not (Test-Path -LiteralPath $JournalPath -PathType Leaf)) { return @() }
    $lines = @(Get-Content -LiteralPath $JournalPath -Tail 120)
    return @($lines | Where-Object {
        $_ -match 'startup-checks|startup-ready|runner-start|cycle-start|child-start|child-exit|retry|cycle-complete|runner-exception|hard-stop|done'
    } | Select-Object -Last 8)
}

function Get-RecentSemanticEvents {
    param([string[]]$LogTail)

    if ($null -eq $LogTail) { return @() }
    $pattern = 'PASS|FAIL|CHECKPOINT|NATIVE|BUILD|RESOURCE|FRAME|CANONICAL|FIRST_LOSS|CONFORMANCE|CALL|C_A|S1_2|SELF_EMIT|STAGE1|HARD_STOP|NEXT_SAFE_ACTION'
    $events = @($LogTail | Where-Object { $_ -match $pattern } | Select-Object -Last 18)
    return @($events | ForEach-Object { Get-CompactText -Text $_ -MaxLength 155 })
}

function Get-HealthState {
    param(
        $ProcessSnapshot,
        $JournalItem,
        $LogItem,
        $BatonItem
    )

    if (Test-Path -LiteralPath $HardStopPath -PathType Leaf) { return 'POSSIBLE STALL' }
    if (Test-Path -LiteralPath $DonePath -PathType Leaf) { return 'ACTIVE' }
    $journalAge = Get-AgeSeconds -Item $JournalItem
    $logAge = Get-AgeSeconds -Item $LogItem
    $batonAge = Get-AgeSeconds -Item $BatonItem
    $activityAge = @($journalAge, $logAge, $batonAge) | Where-Object { $null -ne $_ } | Measure-Object -Minimum
    $minimumAge = if ($activityAge.Count -gt 0) { $activityAge.Minimum } else { $null }

    if ($ProcessSnapshot.RunnerFound -and $ProcessSnapshot.ChildFound) {
        if ($null -ne $minimumAge -and $minimumAge -gt 300) { return 'POSSIBLE STALL' }
        return 'ACTIVE'
    }
    if ($ProcessSnapshot.RunnerFound) { return 'WAITING BETWEEN CYCLES' }
    return 'STOPPED'
}

function Show-Dashboard {
    $processSnapshot = Get-ProcessSnapshot
    $runner = $processSnapshot.Runner
    $child = $processSnapshot.Child
    $logItem = Get-CurrentLog
    $journalItem = if (Test-Path -LiteralPath $JournalPath -PathType Leaf) { Get-Item -LiteralPath $JournalPath } else { $null }
    $batonItem = if (Test-Path -LiteralPath $BatonPath -PathType Leaf) { Get-Item -LiteralPath $BatonPath } else { $null }
    $candidateItem = if (Test-Path -LiteralPath $CandidatePath -PathType Leaf) { Get-Item -LiteralPath $CandidatePath } else { $null }
    $canonicalItem = if (Test-Path -LiteralPath $CanonicalPath -PathType Leaf) { Get-Item -LiteralPath $CanonicalPath } else { $null }
    $batonLines = if ($null -ne $batonItem) { @(Get-Content -LiteralPath $BatonPath) } else { @() }
    $logTail = Get-BoundedLogTail -LogItem $logItem
    $candidate = Get-CachedFileSnapshot -Path $CandidatePath -Key 'candidate'
    $canonical = Get-CachedFileSnapshot -Path $CanonicalPath -Key 'canonical'
    $health = Get-HealthState -ProcessSnapshot $processSnapshot -JournalItem $journalItem -LogItem $logItem -BatonItem $batonItem
    $now = Get-Date
    $phase = Get-FieldValue -Lines $batonLines -Name 'PHASE'
    $checkpointName = Get-LastCheckpointName -Lines $batonLines
    $hasCanonicalFirstLoss = Test-CanonicalFirstLoss -Lines $batonLines -CheckpointName $checkpointName
    $canonicalProbeValue = Get-CanonicalProbeValue -Lines $batonLines
    $canonicalConformanceValue = Get-CanonicalConformanceValue -Lines $batonLines -HasFirstLoss $hasCanonicalFirstLoss
    $canonicalLossRepairValue = Get-CanonicalLossRepairValue -Phase $phase -Lines $batonLines
    $canonicalLossDetails = Get-CanonicalLossDetails -Lines $batonLines -CheckpointName $checkpointName
    $phaseAControlValue = Get-PhaseAControlValue -Lines $batonLines -Phase $phase
    $nativeBuildValue = Get-FirstAvailableFieldValue -Lines $batonLines -Names @('NATIVE_BUILD', 'NATIVE_STATUS')
    $resourceValue = Get-FirstAvailableFieldValue -Lines $batonLines -Names @('RESOURCE_CONTRACT', 'RESOURCE_STATUS', 'RESOURCE')
    $s12Value = Get-FieldValue -Lines $batonLines -Name 'S1_2'
    $s16Value = Get-FieldValue -Lines $batonLines -Name 'S1_6'
    $selfEmitValue = Get-FirstAvailableFieldValue -Lines $batonLines -Names @('SELF_EMIT_STATUS', 'SELF_EMIT')
    $stage1Value = Get-FirstAvailableFieldValue -Lines $batonLines -Names @('STAGE1_STATUS', 'STAGE1')

    Clear-Host
    Write-ColorLine '===============================================' 'Cyan'
    Write-ColorLine '        S3 STAGE1 AUTONOMOUS - LIVE' 'Cyan'
    Write-ColorLine '===============================================' 'Cyan'
    Write-Host ('TIME:     {0}' -f $now.ToString('yyyy-MM-dd HH:mm:ss'))
    $runnerText = if ($null -ne $runner) { 'PID {0}     RUNNING' -f $runner.ProcessId } else { 'STOPPED' }
    $childText = if ($null -ne $child) { 'PID {0}     RUNNING' -f $child.ProcessId } else { 'STOPPED' }
    Write-Host ('UPTIME:   {0}' -f (Format-Uptime -CreationDate $(if ($null -ne $runner) { $runner.CreationDate } else { $null })))
    Write-Host ('RUNNER:   {0}' -f $runnerText) -ForegroundColor $(if ($null -ne $runner) { 'Green' } else { 'Red' })
    Write-Host ('CHILD:    {0}' -f $childText) -ForegroundColor $(if ($null -ne $child) { 'Green' } else { 'Yellow' })
    Write-Host ('LOCK:     {0}' -f $processSnapshot.LockStatus) -ForegroundColor $(if ($processSnapshot.LockStatus -eq 'VALID') { 'Green' } else { 'Yellow' })
    Write-Host ('ACTIVITY: {0} ({1})' -f $health, (Format-Age -Seconds (Get-AgeSeconds -Item $logItem))) -ForegroundColor $(if ($health -eq 'ACTIVE') { 'Green' } elseif ($health -eq 'POSSIBLE STALL') { 'Red' } else { 'Yellow' })

    if (Test-Path -LiteralPath $HardStopPath -PathType Leaf) {
        Write-ColorLine '===============================================' 'Red'
        Write-ColorLine '                HARD STOP' 'Red'
        Write-ColorLine '===============================================' 'Red'
        Get-Content -LiteralPath $HardStopPath -Tail 6 | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    }
    elseif (Test-Path -LiteralPath $DonePath -PathType Leaf) {
        Write-ColorLine '===============================================' 'Green'
        Write-ColorLine '                STAGE1 DONE' 'Green'
        Write-ColorLine '===============================================' 'Green'
        Get-Content -LiteralPath $DonePath -Tail 6 | ForEach-Object { Write-Host $_ -ForegroundColor Green }
    }

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'PIPELINE' 'Cyan'
    Write-GateLine 'Phase A / Control' $phaseAControlValue
    Write-GateLine 'Fresh Native Build' $nativeBuildValue
    Write-GateLine 'Resource Contract' $resourceValue
    Write-GateLine 'Canonical Probe' $canonicalProbeValue
    Write-GateLine 'Canonical Loss Repair' $canonicalLossRepairValue
    Write-GateLine 'S1.2' $s12Value
    Write-GateLine 'Self Emit' $selfEmitValue
    Write-GateLine 'Stage1' $stage1Value

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'CHECKPOINT' 'Cyan'
    Write-Host ('PHASE:          {0}' -f $phase)
    Write-Host ('LAST COMPLETED: {0}' -f $checkpointName)
    Write-Host ('FIRST OPEN:     {0}' -f (Get-CompactText -Text $s12Value -MaxLength 145))
    Write-Host ('NEXT ACTION:    {0}' -f (Get-CompactText -Text (Get-FieldValue -Lines $batonLines -Name 'NEXT_SAFE_ACTION') -MaxLength 145))

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'CANDIDATE / CANONICAL' 'Cyan'
    Write-Host ('CANDIDATE SHA:       {0}' -f $candidate.Sha256)
    Write-Host ('CANDIDATE LAST WRITE: {0}' -f $candidate.LastWrite)
    $canonicalColor = if ($canonical.Sha256 -eq $ExpectedCanonicalSha) { 'Green' } else { 'Red' }
    $canonicalState = if ($canonical.Sha256 -eq $ExpectedCanonicalSha) { 'PASS' } else { 'FAIL' }
    Write-Host ('CANONICAL SHA:       {0}' -f $canonical.Sha256)
    Write-Host ('CANONICAL FILE:      {0}' -f $canonicalState) -ForegroundColor $canonicalColor
    Write-Host ('CANONICAL PROBE:     {0}' -f $canonicalProbeValue) -ForegroundColor (Get-GateColor -Status (Convert-ToGateStatus -Value $canonicalProbeValue))
    Write-Host ('CONFORMANCE:         {0}' -f $canonicalConformanceValue) -ForegroundColor $(if ($canonicalConformanceValue -eq 'FIRST LOSS') { 'Yellow' } else { 'Gray' })
    if ($canonicalState -eq 'FAIL') { Write-ColorLine '!!! CANONICAL INTEGRITY FAIL !!!' 'Red' }

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'CYCLE / LOG' 'Cyan'
    $cycleName = if ($null -ne $logItem -and $logItem.Name -match '^cycle-(\d+)-') { $Matches[1] } else { 'UNKNOWN' }
    Write-Host ('CYCLE:              {0}' -f $cycleName)
    Write-Host ('SEGMENT:            {0}' -f $(if ($null -ne $logItem) { $logItem.Name } else { 'NONE' }))
    Write-Host ('CURRENT LOG:        {0}' -f $(if ($null -ne $logItem) { $logItem.Name } else { 'NONE' }))
    Write-Host ('LOG SIZE:           {0:N2} MiB' -f $(if ($null -ne $logItem) { $logItem.Length / 1MB } else { 0 }))
    Write-Host ('LAST WRITE:         {0}' -f $(if ($null -ne $logItem) { $logItem.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'NONE' }))
    Write-Host ('LAST ACTIVITY:      {0}' -f (Format-Age -Seconds (Get-AgeSeconds -Item $logItem)))

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'JOURNAL' 'Cyan'
    $journalEvents = Get-RecentJournalEvents
    if ($journalEvents.Count -eq 0) { Write-Host '  waiting for lifecycle events...' }
    foreach ($event in $journalEvents) { Write-Host ('  {0}' -f (Get-CompactText -Text $event -MaxLength 155)) }

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'RECENT SEMANTIC EVENTS' 'Cyan'
    $semanticEvents = Get-RecentSemanticEvents -LogTail $logTail
    if ($semanticEvents.Count -eq 0) { Write-Host '  waiting for semantic events...' }
    foreach ($event in $semanticEvents) { Write-Host ('  {0}' -f $event) }

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'GATES' 'Cyan'
    Write-ColorLine 'CONTROL' 'DarkCyan'
    Write-GateLine 'COMPARE' (Get-FieldValue -Lines $batonLines -Name 'COMPARE')
    Write-GateLine 'BRANCH3' (Get-FieldValue -Lines $batonLines -Name 'BRANCH3')
    Write-GateLine 'T' (Get-FieldValue -Lines $batonLines -Name 'T')
    Write-GateLine 'WHILE' (Get-FieldValue -Lines $batonLines -Name 'WHILE')
    Write-ColorLine 'V3' 'DarkCyan'
    Write-GateLine 'D' (Get-FieldValue -Lines $batonLines -Name 'D')
    Write-GateLine 'V' (Get-FieldValue -Lines $batonLines -Name 'V')
    Write-GateLine 'M' (Get-FieldValue -Lines $batonLines -Name 'M')
    Write-GateLine 'I/O/R' (Get-FieldValue -Lines $batonLines -Name 'I_O_R')
    Write-GateLine 'C/A' (Get-FieldValue -Lines $batonLines -Name 'C_A')
    Write-GateLine 'T' (Get-FieldValue -Lines $batonLines -Name 'T')
    Write-ColorLine 'CURRENT' 'DarkCyan'
    Write-GateLine 'NATIVE BUILD' $nativeBuildValue
    Write-GateLine 'RESOURCE' $resourceValue
    Write-GateLine 'CANONICAL PROBE' $canonicalProbeValue
    Write-GateLine 'S1.2' $s12Value
    Write-GateLine 'S1.6' $s16Value
    Write-GateLine 'SELF EMIT' $selfEmitValue
    Write-GateLine 'STAGE1' $stage1Value

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'FIRST CANONICAL LOSS' 'Cyan'
    if ($null -eq $canonicalLossDetails) {
        Write-Host '  waiting for canonical probe...'
    }
    else {
        Write-Host ('FUNCTION:  {0}' -f $canonicalLossDetails.Function)
        Write-Host ('SPAN:      {0}' -f $canonicalLossDetails.Span)
        Write-Host ('CONSTRUCT: {0}' -f $canonicalLossDetails.Construct)
        Write-Host ('CAUSE:     {0}' -f (Get-CompactText -Text $canonicalLossDetails.Cause -MaxLength 155))
    }

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'PROCESS HEALTH' 'Cyan'
    Write-Host ('RUNNER PID:   {0}' -f $(if ($null -ne $runner) { $runner.ProcessId } else { 'NONE' }))
    Write-Host ('CHILD PID:    {0}' -f $(if ($null -ne $child) { $child.ProcessId } else { 'NONE' }))
    Write-Host ('CHILD START:  {0}' -f $(if ($null -ne $child) { $child.CreationDate } else { 'NONE' }))
    $childCommand = if ($null -ne $child) { Get-CompactText -Text $child.CommandLine -MaxLength 150 } else { 'NONE' }
    Write-Host ('CHILD COMMAND: {0}' -f $childCommand)
    Write-Host ('HEALTH:       {0}' -f $health) -ForegroundColor $(if ($health -eq 'ACTIVE') { 'Green' } elseif ($health -eq 'POSSIBLE STALL') { 'Red' } else { 'Yellow' })
    Write-Host ('SINCE JOURNAL: {0}' -f (Format-Age -Seconds (Get-AgeSeconds -Item $journalItem)))
    Write-Host ('SINCE LOG:     {0}' -f (Format-Age -Seconds (Get-AgeSeconds -Item $logItem)))
    Write-Host ('SINCE BATON:   {0}' -f (Format-Age -Seconds (Get-AgeSeconds -Item $batonItem)))
    Write-Host ('SINCE CANDIDATE: {0}' -f (Format-Age -Seconds (Get-AgeSeconds -Item $candidateItem)))

    Write-ColorLine '' 'Gray'
    Write-ColorLine 'Ctrl+C = close ONLY this dashboard' 'Yellow'
    Write-ColorLine 'CLOSING THIS WINDOW DOES NOT STOP THE RUNNER' 'Yellow'
}

try {
    $Host.UI.RawUI.WindowTitle = 'S3 Stage1 Autonomous - Live'
}
catch {
}

while ($true) {
    try {
        Show-Dashboard
    }
    catch {
        Clear-Host
        Write-ColorLine 'S3 STAGE1 AUTONOMOUS - LIVE' 'Cyan'
        Write-ColorLine ('Watcher read error: {0}' -f $_.Exception.Message) 'Red'
        Write-ColorLine 'The watcher will retry without modifying the runner.' 'Yellow'
    }
    Start-Sleep -Seconds $RefreshSeconds
}
