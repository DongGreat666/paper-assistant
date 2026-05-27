param(
    [int]$KeepLines = 100,
    [string[]]$LogFiles = @(
        "reflex_output.log",
        "reflex_backend.log",
        "reflex-run-*.log"
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

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
            return $true
        }

        Set-Content -LiteralPath $Path -Value $tail -Encoding UTF8 -ErrorAction Stop
        return $true
    }
    catch {
        Write-Warning "Skipped $Path because it is unavailable: $($_.Exception.Message)"
        return $false
    }
}

foreach ($pattern in $LogFiles) {
    Get-ChildItem -Path $ProjectRoot -File -Filter $pattern -ErrorAction SilentlyContinue |
        ForEach-Object {
            if (Trim-LogFile -Path $_.FullName -Lines $KeepLines) {
                Write-Host "Trimmed $($_.Name) to the latest $KeepLines lines."
            }
        }
}
