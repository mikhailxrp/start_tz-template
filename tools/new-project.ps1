<#
.SYNOPSIS
    Creates a new TZ project folder from the tz-template.

.DESCRIPTION
    Copies the folder skeleton, reference documents, tools and Claude Code
    commands into a new folder. Initializes a git repository.

.PARAMETER Name
    Project name. Becomes the folder name.

.PARAMETER Path
    Where to create it. Defaults to the folder next to tz-template.

.PARAMETER NoGit
    Skip git initialization.

.EXAMPLE
    .\tools\new-project.ps1 -Name "acme-electronics"

.EXAMPLE
    .\tools\new-project.ps1 -Name "acme-electronics" -Path "D:\Development\clients"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [string]$Path = "..",

    [switch]$NoGit
)

$ErrorActionPreference = "Stop"

$templateRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path $Path)) {
    Write-Host "Path not found: $Path" -ForegroundColor Red
    exit 1
}

$target = Join-Path (Resolve-Path $Path) $Name

if (Test-Path $target) {
    Write-Host "Directory already exists: $target" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Creating project: $Name" -ForegroundColor Cyan
Write-Host "Path: $target"
Write-Host ""

# --- Copy files -----------------------------------------------------------

Copy-Item -Path (Join-Path $templateRoot "template") -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot "reference") -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot "tools")     -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot ".claude")   -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot "CLAUDE.md") -Destination $target

# The project-creation script itself is not needed inside a project
Remove-Item (Join-Path $target "tools\new-project.ps1") -ErrorAction SilentlyContinue

# Blank TZ document from the template
Copy-Item -Path (Join-Path $templateRoot "reference\template-tz.md") `
          -Destination (Join-Path $target "01-tz\tz.md")

# --- Project README -------------------------------------------------------
# README text lives in template/README.md with placeholders.
# This script contains no Cyrillic on purpose: PowerShell 5.1 mangles it
# whenever the .ps1 file gets saved without a BOM.

$stamp = Get-Date -Format "yyyy-MM-dd"
$readmePath = Join-Path $target "README.md"

if (Test-Path $readmePath) {
    $readme = Get-Content -Path $readmePath -Raw -Encoding UTF8
    $readme = $readme -replace '\{\{PROJECT_NAME\}\}', $Name
    $readme = $readme -replace '\{\{DATE\}\}', $stamp
    Set-Content -Path $readmePath -Value $readme -Encoding UTF8 -NoNewline
}
else {
    Write-Host "Warning: template/README.md not found, project README skipped" -ForegroundColor Yellow
}

# --- .gitignore -----------------------------------------------------------

$gitignore = @"
*.tmp
*.bak
~`$*
.DS_Store
Thumbs.db
__pycache__/
"@

Set-Content -Path (Join-Path $target ".gitignore") -Value $gitignore -Encoding UTF8

# --- Git ------------------------------------------------------------------

if (-not $NoGit) {
    # Git writes hook output to stderr. With ErrorActionPreference = "Stop"
    # PowerShell treats that as an exception even on success.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    Push-Location $target
    try {
        git init -q
        git config core.hooksPath .githooks
        git config core.autocrlf false
        git add . 2>$null
        git commit -q -m "init: project skeleton from tz-template" 2>$null

        git rev-parse --verify HEAD *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Git: repository initialized, first commit created" -ForegroundColor Green
        }
        else {
            Write-Host "Git: repository initialized, commit skipped" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Git skipped: $_" -ForegroundColor Yellow
    }
    finally {
        Pop-Location
        $ErrorActionPreference = $prevEAP
    }
}

# --- Summary --------------------------------------------------------------

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Put the filled brief into 00-input\brief.md"
Write-Host "  2. cd `"$target`""
Write-Host "  3. claude"
Write-Host "  4. /tz-start"
Write-Host ""
