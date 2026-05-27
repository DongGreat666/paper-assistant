param(
    [int]$KeepLines = 100,
    [int]$TrimIntervalSeconds = 10,
    [string]$OutputLog = "reflex_output.log",
    [string]$BackendLog = "reflex_backend.log",
    [string[]]$ReflexArgs = @("run")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutputLogPath = Join-Path $ProjectRoot $OutputLog
$BackendLogPath = Join-Path $ProjectRoot $BackendLog

function Trim-LogFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [int]$Lines
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    try {
        $tail = Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction Stop
        if ($null -eq $tail) {
            Clear-Content -LiteralPath $Path -ErrorAction Stop
            return
        }

        Set-Content -LiteralPath $Path -Value $tail -Encoding UTF8 -ErrorAction Stop
    }
    catch {
        Write-Warning "Skipped $Path because it is unavailable: $($_.Exception.Message)"
    }
}

function Limit-ReflexLogs {
    Trim-LogFile -Path $OutputLogPath -Lines $KeepLines
    Trim-LogFile -Path $BackendLogPath -Lines $KeepLines
}

Limit-ReflexLogs

$watcher = Start-Job -ScriptBlock {
    param($Paths, $Lines, $IntervalSeconds)

    function Trim-LogFileInJob {
        param(
            [Parameter(Mandatory = $true)]
            [string]$Path,
            [Parameter(Mandatory = $true)]
            [int]$Lines
        )

        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            return
        }

        try {
            $tail = Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction Stop
            if ($null -eq $tail) {
                Clear-Content -LiteralPath $Path -ErrorAction Stop
                return
            }

            Set-Content -LiteralPath $Path -Value $tail -Encoding UTF8 -ErrorAction Stop
        }
        catch {
            # The app may be writing the file at the same moment. The next pass will try again.
        }
    }

    while ($true) {
        foreach ($path in $Paths) {
            Trim-LogFileInJob -Path $path -Lines $Lines
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
} -ArgumentList @($OutputLogPath, $BackendLogPath), $KeepLines, $TrimIntervalSeconds

Push-Location $ProjectRoot
$exitCode = 0
try {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] reflex $($ReflexArgs -join ' ')" |
        Add-Content -LiteralPath $OutputLogPath -Encoding UTF8

    $lineCount = 0
    & reflex @ReflexArgs 2>&1 | ForEach-Object {
        $line = $_.ToString()
        $line | Add-Content -LiteralPath $OutputLogPath -Encoding UTF8
        Write-Host $line

        $lineCount += 1
        if (($lineCount % 20) -eq 0) {
            Limit-ReflexLogs
        }
    }

    $exitCode = $LASTEXITCODE
}
finally {
    Limit-ReflexLogs
    Stop-Job -Job $watcher -ErrorAction SilentlyContinue | Out-Null
    Remove-Job -Job $watcher -Force -ErrorAction SilentlyContinue | Out-Null
    Pop-Location
}

exit $exitCode
