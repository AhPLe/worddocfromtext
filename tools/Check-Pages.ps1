# Check-Pages.ps1 - M4 owner-side page gate (real Word, real Aptos).
#
# Counts the pages of a rendered .docx via Word COM and fails (exit 1)
# when over budget. The one-page constraint is load-bearing for
# submissions; the rendered page count is the ground truth.
#
# Usage:
#   .\tools\Check-Pages.ps1 .\analyst.docx
#   .\tools\Check-Pages.ps1 .\analyst.docx -MaxPages 2
#
# Typical flow (one command per line; PowerShell 5 has no &&):
#   python -m builder .\RESUME_MASTER.md --render --cut analyst --spacing tight --template .\template.docx --out .\analyst.docx
#   .\tools\Check-Pages.ps1 .\analyst.docx
#
# Notes: opens Word invisibly and quits it afterwards. If a stray
# WINWORD.EXE lingers after a crash, close it from Task Manager.
# Verification level: parse-checked only (no Word in Claude's sandbox);
# please report the first real run.

param(
    [Parameter(Mandatory = $true)][string]$Path,
    [int]$MaxPages = 1
)

$resolved = (Resolve-Path $Path).Path
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    # Open(FileName, ConfirmConversions:=$false, ReadOnly:=$true)
    $doc = $word.Documents.Open($resolved, $false, $true)
    $pages = $doc.ComputeStatistics(2)  # 2 = wdStatisticPages
    $doc.Close($false)
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}

Write-Host ("{0}: {1} page(s) (budget {2})" -f $Path, $pages, $MaxPages)
if ($pages -gt $MaxPages) {
    Write-Warning "over the page budget - try --spacing tight, trim a cut (canon: Scigenesis to 2-3 bullets), or reduce top/bottom margins"
    exit 1
}
exit 0
