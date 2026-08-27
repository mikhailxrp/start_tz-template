<#
.SYNOPSIS
    Создаёт папку нового проекта ТЗ на основе шаблона.

.DESCRIPTION
    Копирует скелет папок, эталонные документы, инструменты и команды
    Claude Code в новую папку. Инициализирует git-репозиторий.

.PARAMETER Name
    Имя проекта. Станет именем папки.

.PARAMETER Path
    Куда создать. По умолчанию — папка рядом с tz-template.

.PARAMETER NoGit
    Не инициализировать git.

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

# --- Копирование ----------------------------------------------------------

Copy-Item -Path (Join-Path $templateRoot "template") -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot "reference") -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot "tools")     -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot ".claude")   -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot "CLAUDE.md") -Destination $target

# Скрипт создания проектов внутри проекта не нужен
Remove-Item (Join-Path $target "tools\new-project.ps1") -ErrorAction SilentlyContinue

# Пустой файл ТЗ из шаблона
Copy-Item -Path (Join-Path $templateRoot "reference\template-tz.md") `
          -Destination (Join-Path $target "01-tz\tz.md")

# --- README проекта -------------------------------------------------------

$stamp = Get-Date -Format "yyyy-MM-dd"
$fence = '```'

$readme = @"
# $Name

Создан: $stamp
Из шаблона: tz-template

## Порядок работы

1. Положить заполненный бриф в ``00-input/brief.md``
2. Приложения — в ``00-input/attachments/``
3. Открыть папку в Claude Code: ``claude``
4. Выполнять команды по порядку

$fence
/tz-start                              инвентаризация, вопросы клиенту
/tz-model                              разделы 4-6: глоссарий, роли, состояния
/tz-scenarios                          раздел 7: сценарии
/tz-modules 8.1 8.2 8.3 8.18           каталог, карточка, поиск, контент
/tz-modules 8.4 8.5 8.6 8.7            корзина, оформление, оплата, доставка
/tz-modules 8.8 8.9 8.10 8.11          заказы, склад, возвраты, скидки
/tz-modules 8.12 8.13 8.14 8.15 8.16 8.17   кабинеты, админка, уведомления
/tz-rules                              разделы 9-14
/tz-summary                            разделы 1-3
/tz-review                             ревью НОВОЙ сессией
$fence

5. Коммит после каждой сессии

$fence
git commit -am "tz: section 8.5 checkout, 12 requirements"
$fence

## Гейты

Нельзя идти дальше, пока:

| Этап | Условие |
|---|---|
| После /tz-start | вопросы отправлены клиенту |
| После /tz-model | разделы 4-6 заполнены |
| После каждого /tz-modules | check_tz.py без ошибок ERROR |
| Перед /tz-summary | разделы 4-13 закрыты |
| Перед передачей в SDD | ревью пройдено |

## Проверка

$fence
python tools\check_tz.py 01-tz\tz.md
python tools\check_tz.py 01-tz\tz.md --strict
$fence

## Структура

$fence
00-input/     данные клиента, только чтение
01-tz/        рабочая папка: tz.md, decisions.md, coverage.md
02-sdd/       следующий этап
reference/    эталоны
tools/        валидатор
$fence
"@

Set-Content -Path (Join-Path $target "README.md") -Value $readme -Encoding UTF8

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
    }
}

# --- Итог -----------------------------------------------------------------

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Put the filled brief into 00-input\brief.md"
Write-Host "  2. cd `"$target`""
Write-Host "  3. claude"
Write-Host "  4. /tz-start"
Write-Host ""