param(
    [string]$VersionsDir = ".\migrations\versions"
)

if (-not (Test-Path $VersionsDir)) {
    Write-Host "VersionsDir not found: $VersionsDir" -ForegroundColor Red
    exit 1
}

# Collect all *.py migrations
$files = Get-ChildItem -Path $VersionsDir -Filter "*.py" -File
if (-not $files) {
    Write-Host "No migration files found in $VersionsDir" -ForegroundColor Yellow
    exit 0
}

# Data structures
$revs  = @{}   # revision -> file name
$parentsMap = @{} # revision -> list of parent revisions (down_revisions)
$childrenMap = @{} # parent -> list of children revisions

# Regex helpers
$rxRev  = [regex]"revision\s*=\s*['""]([^'""]+)['""]"
# Matches: down_revision = None
#          down_revision = 'abcd'
#          down_revision = ('abcd', 'efgh')  or ["abcd","efgh"]
$rxDown = [regex]"down_revision\s*=\s*(None|['""][^'""]+['""]|\((?>[^()]+|\((?<DEPTH>)|\)(?<-DEPTH>))*\)|\[[^\]]*\])"

function Parse-DownRevisions([string]$text) {
    $m = $rxDown.Match($text)
    if (-not $m.Success) { return @() }

    $raw = $m.Groups[1].Value.Trim()
    if ($raw -eq "None") { return @() }

    # Normalize: if it's a plain string 'abc' or "abc"
    if ($raw -match "^['""]([^'""]+)['""]$") {
        return @($matches[1])
    }

    # If it's a tuple/list, extract all quoted strings inside
    $listMatches = [regex]::Matches($raw, "['""]([^'""]+)['""]")
    $vals = @()
    foreach ($lm in $listMatches) {
        $vals += $lm.Groups[1].Value
    }
    return $vals
}

# Parse each file
foreach ($f in $files) {
    $content = Get-Content -LiteralPath $f.FullName -Raw

    $revMatch = $rxRev.Match($content)
    if (-not $revMatch.Success) {
        Write-Host "WARN: No 'revision = ...' in $($f.Name)" -ForegroundColor Yellow
        continue
    }
    $rev = $revMatch.Groups[1].Value
    $revs[$rev] = $f.Name

    $parents = Parse-DownRevisions $content
    $parentsMap[$rev] = $parents

    foreach ($p in $parents) {
        if (-not $childrenMap.ContainsKey($p)) { $childrenMap[$p] = @() }
        $childrenMap[$p] += $rev
    }
}

# Heads: revs that are not listed as a parent (i.e., have no children)
$allRevs = $revs.Keys
$allChildren = $childrenMap.Values | ForEach-Object { $_ } | Select-Object -Unique
$heads = $allRevs | Where-Object { $allChildren -notcontains $_ }

# Bases: revs with no parents
$bases = $allRevs | Where-Object { -not $parentsMap[$_] -or $parentsMap[$_].Count -eq 0 }

# Orphans: referenced parents that aren't present
$referencedParents = $parentsMap.Values | ForEach-Object { $_ } | Select-Object -Unique
$orphans = $referencedParents | Where-Object { -not $revs.ContainsKey($_) }

# Cycle detection (DFS)
$visited = @{}
$inStack = @{}
$cycles  = New-Object System.Collections.Generic.List[System.String]

function DFS([string]$node, [System.Collections.Generic.List[string]]$path) {
    if ($inStack[$node]) {
        # Found a cycle
        $startIndex = $path.IndexOf($node)
        if ($startIndex -ge 0) {
            $cyclePath = $path[$startIndex..($path.Count-1)] + @($node)
            $cycles.Add(($cyclePath -join " -> "))
        } else {
            $cycles.Add(($path + @($node) -join " -> "))
        }
        return
    }
    if ($visited[$node]) { return }

    $visited[$node] = $true
    $inStack[$node] = $true

    $children = @()
    if ($childrenMap.ContainsKey($node)) { $children = $childrenMap[$node] }

    foreach ($child in $children) {
        $newPath = New-Object System.Collections.Generic.List[string]
        $path | ForEach-Object { [void]$newPath.Add($_) }
        [void]$newPath.Add($child)
        DFS $child $newPath
    }

    $inStack[$node] = $false
}

foreach ($r in $allRevs) {
    if (-not $visited[$r]) {
        $start = New-Object System.Collections.Generic.List[string]
        [void]$start.Add($r)
        DFS $r $start
    }
}

# Output summary
Write-Host "Analyzed $($revs.Count) migration(s) in $VersionsDir" -ForegroundColor Cyan
Write-Host "Bases  (down_revision=None): $($bases.Count)" -ForegroundColor Gray
if ($bases) { $bases -join ", " | Write-Host }
Write-Host "Heads  (no children):       $($heads.Count)" -ForegroundColor Gray
if ($heads) { $heads -join ", " | Write-Host }
Write-Host "Orphan parent refs:         $($orphans.Count)" -ForegroundColor Gray
if ($orphans) { $orphans -join ", " | Write-Host }

if ($cycles.Count) {
    Write-Host ""
    Write-Host "CYCLES DETECTED ($($cycles.Count)):" -ForegroundColor Red
    $i = 1
    foreach ($c in $cycles | Select-Object -Unique) {
        Write-Host ("  {0}. {1}" -f $i, $c) -ForegroundColor Red
        $i++
    }
} else {
    Write-Host ""
    Write-Host "No cycles detected ✅" -ForegroundColor Green
}