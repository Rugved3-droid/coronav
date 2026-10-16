# run_batch_episodes.ps1
# Runs each episode in an isolated subprocess to avoid SOFA crash propagation.
# Usage: .\run_batch_episodes.ps1 -Mode wire_only -Offsets 5,6,7,8,9,10,11,12,13,14 -Steps 120
param(
    [string]$Mode   = "wire_only",
    [int[]] $Offsets = @(0),
    [int]   $Steps   = 120
)

$env:SOFA_ROOT     = "D:\steve\deps\SOFA_v23.06.00_Win64"
$env:PYTHONPATH    = "D:\steve\deps\SOFA_v23.06.00_Win64\plugins\SofaPython3\lib\python3\site-packages"
$env:PATH          = "D:\conda\envs\steve;D:\conda\envs\steve\Scripts;D:\conda\Scripts;D:\conda;" + $env:PATH
$env:PYTHONIOENCODING = "utf-8"
# API key must be set in environment before calling this script

$PY  = "D:\conda\envs\steve\python.exe"
$RUN = "D:\steve\pilot\run_coronary.py"

foreach ($offset in $Offsets) {
    $epNum = $offset + 1   # global episode number (1-indexed)
    $epTag = "ep{0:D2}" -f $epNum
    $outDir = "D:\steve\pilot\runs\batch_${Mode}_${epTag}"
    Write-Host "`n=== $Mode  offset=$offset  (ep$epNum)  out=$outDir ==="
    & $PY -u $RUN --mode $Mode --episodes 1 --steps $Steps --episode-offset $offset --out $outDir
    $exit = $LASTEXITCODE
    Write-Host "--- exit=$exit ---"
}
Write-Host "`nBatch done."
