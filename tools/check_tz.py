#!/usr/bin/env python3
"""
Валидатор технического задания.

Проверяет то, что можно проверить механически:
формат требований, дубли ID, пропущенные поля, остатки шаблона,
запрещённые формулировки, целостность ссылок.

Использование:
    python3 check_tz.py 01-tz/tz.md
    python3 check_tz.py 01-tz/tz.md --strict   # ненулевой код возврата при ошибках
"""

import re
import sys
from collections import Counter, defaultdict

# --- Конфигурация ---------------------------------------------------------

MODULES = {
    "HOME", "CAT", "CARD", "SRCH", "CART", "CHK", "PAY", "SHIP", "ORD", "STOCK",
    "RET", "DISC", "ACC", "B2B", "MGR", "ADM", "AUTH", "NOTIF", "SEO",
    "INT", "CNT", "MIGR",
}

NFR_CATEGORIES = {"PERF", "LOAD", "SEC", "AVL", "LEGAL", "OPS", "COMP"}

PRIORITIES = {"MUST", "SHOULD", "COULD", "WON'T"}
QUEUES = {"MVP", "2", "нет"}

BANNED_WORDS = [
    "удобно", "удобн", "быстро", "быстр", "красиво", "красив",
    "современн", "интуитивн", "оптимальн", "надёжн", "надежн",
    "гибк", "при необходимости", "и т.п.", "и так далее",
    "желательно", "по возможности", "и др.",
]

# Разделы, без которых SDD не начинается
CRITICAL_SECTIONS = {
    "3.1": "Приоритет проекта",
    "4": "Глоссарий",
    "5.2": "Матрица прав",
    "6.3": "Диаграммы состояний",
    "10.1": "Источник истины по данным",
    "11.6": "Эксплуатация",
    "14": "Критерии приёмки",
}

TEMPLATE_LEFTOVERS = [
    "[УДАЛИТЬ ЕСЛИ",
    "Заполнить:",
    "ЗАПОЛНИТЬ",
]

REQ_HEADER = re.compile(
    r"^###\s+(FR-([A-Z][A-Z0-9]*)-(\d{3})|NFR-([A-Z]+)-(\d{3})|BR-(\d{3}))(/[БР])?\s*·\s*(.+)$"
)
ANY_ID = re.compile(r"\b((?:FR-[A-Z][A-Z0-9]*|NFR-[A-Z]+|BR|AS|Q|C|RISK)-\d{3})(/[БР])?\b")


class Issue:
    def __init__(self, severity, line, message):
        self.severity = severity  # ERROR | WARN | INFO
        self.line = line
        self.message = message


def parse_requirements(lines):
    """Возвращает список блоков требований: (id, маркер, заголовок, строка, тело)."""
    blocks = []
    current = None
    in_code = False
    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = REQ_HEADER.match(line.strip())
        if m:
            if current:
                blocks.append(current)
            req_id = m.group(1)
            marker = (m.group(7) or "").lstrip("/")
            title = m.group(8).strip()
            current = {"id": req_id, "marker": marker, "title": title,
                       "line": i, "body": []}
        elif current is not None:
            if line.startswith("## ") or line.startswith("---"):
                blocks.append(current)
                current = None
            else:
                current["body"].append(line)
    if current:
        blocks.append(current)
    return blocks


def check_requirement(block):
    issues = []
    body = "\n".join(block["body"])
    rid = block["id"]
    ln = block["line"]

    # Маркер происхождения
    if not block["marker"]:
        issues.append(Issue("ERROR", ln,
            f"{rid}: нет маркера /Б или /Р — происхождение неизвестно"))

    # Модуль из справочника
    if rid.startswith("FR-"):
        module = rid.split("-")[1]
        if module not in MODULES:
            issues.append(Issue("ERROR", ln,
                f"{rid}: модуль '{module}' отсутствует в справочнике"))
        if module == "PRD":
            issues.append(Issue("ERROR", ln,
                f"{rid}: модуль PRD запрещён (конфликт с prd.md), используй CARD"))
    if rid.startswith("NFR-"):
        cat = rid.split("-")[1]
        if cat not in NFR_CATEGORIES:
            issues.append(Issue("ERROR", ln,
                f"{rid}: категория NFR '{cat}' отсутствует в справочнике"))

    is_br = rid.startswith("BR-")

    # Обязательные поля.
    # Бизнес-правила BR имеют иной формат: таблица правил вместо
    # приоритета, роли и критериев приёмки.
    if not is_br:
        if "Приоритет:" not in body:
            issues.append(Issue("ERROR", ln, f"{rid}: нет строки 'Приоритет:'"))
        else:
            pm = re.search(r"Приоритет:\s*([A-Z']+)", body)
            if pm and pm.group(1) not in PRIORITIES:
                issues.append(Issue("ERROR", ln,
                    f"{rid}: приоритет '{pm.group(1)}' вне MoSCoW"))

        if "Очередь:" not in body:
            issues.append(Issue("WARN", ln, f"{rid}: нет строки 'Очередь:'"))
        if "Роль:" not in body:
            issues.append(Issue("WARN", ln, f"{rid}: нет строки 'Роль:'"))
        if "Источник:" not in body:
            issues.append(Issue("WARN", ln, f"{rid}: нет строки 'Источник:'"))

        if "Критерии приёмки" not in body and "Критерии приемки" not in body:
            issues.append(Issue("ERROR", ln, f"{rid}: нет критериев приёмки"))

        if "Требование:" not in body:
            issues.append(Issue("WARN", ln, f"{rid}: нет блока 'Требование:'"))
    else:
        # Бизнес-правило должно содержать таблицу или нумерованные правила
        has_table = "|" in body
        has_rules = re.search(r"^\s*\d+\.", body, re.M)
        if not (has_table or has_rules):
            issues.append(Issue("WARN", ln,
                f"{rid}: бизнес-правило без таблицы и без нумерованных правил"))

    # Запрещённые формулировки
    lowered = body.lower()
    for w in BANNED_WORDS:
        if w in lowered:
            issues.append(Issue("WARN", ln,
                f"{rid}: расплывчатая формулировка — '{w}'"))
            break

    # Подозрительно короткое требование — признак дрейфа формата
    meaningful = [l for l in block["body"] if l.strip()]
    if not is_br and len(meaningful) < 5:
        issues.append(Issue("WARN", ln,
            f"{rid}: тело требования всего {len(meaningful)} строк — "
            f"вероятно, формат сокращён"))

    return issues


def check_document(text):
    lines = text.splitlines()
    issues = []

    blocks = parse_requirements(lines)

    # Дубли ID
    ids = [b["id"] for b in blocks]
    for rid, count in Counter(ids).items():
        if count > 1:
            issues.append(Issue("ERROR", 0,
                f"{rid}: идентификатор использован {count} раза"))

    # Проверка каждого требования
    for b in blocks:
        issues.extend(check_requirement(b))

    # Битые ссылки: ID упомянут, но нигде не определён
    defined = set(ids)
    registry_ids = set(re.findall(r"\|\s*((?:AS|Q|C|RISK)-\d{3})\s*\|", text))
    defined |= registry_ids

    referenced = set()
    for m in ANY_ID.finditer(text):
        referenced.add(m.group(1))

    dangling = sorted(r for r in referenced - defined
                      if not r.endswith("-000"))
    for r in dangling:
        issues.append(Issue("WARN", 0,
            f"{r}: ссылка есть, определения нет"))

    # Остатки шаблона
    for i, line in enumerate(lines, start=1):
        for marker in TEMPLATE_LEFTOVERS:
            if marker in line:
                issues.append(Issue("WARN", i,
                    f"остаток шаблона: {marker}"))
                break

    # Критичные разделы
    for num, name in CRITICAL_SECTIONS.items():
        pattern = re.compile(r"^#+\s*" + re.escape(num) + r"[.\s]", re.M)
        if not pattern.search(text):
            issues.append(Issue("ERROR", 0,
                f"отсутствует раздел {num} «{name}» — SDD не начнётся"))

    return issues, blocks


def report(issues, blocks, path):
    by_module = defaultdict(int)
    markers = Counter()
    priorities = Counter()

    for b in blocks:
        if b["id"].startswith("FR-"):
            by_module[b["id"].split("-")[1]] += 1
        markers[b["marker"] or "нет"] += 1

    errors = [i for i in issues if i.severity == "ERROR"]
    warns = [i for i in issues if i.severity == "WARN"]

    print(f"\n{'='*62}")
    print(f"  ПРОВЕРКА ТЗ: {path}")
    print(f"{'='*62}\n")

    print(f"Требований найдено: {len(blocks)}")
    if by_module:
        print("\nПо модулям:")
        for m, c in sorted(by_module.items(), key=lambda x: -x[1]):
            bar = "█" * min(c, 40)
            print(f"  {m:6} {c:4}  {bar}")

    print("\nМаркеры происхождения:")
    for m, c in markers.most_common():
        label = {"Б": "из брифа", "Р": "решение аналитика",
                 "нет": "БЕЗ МАРКЕРА"}.get(m, m)
        print(f"  {label:20} {c}")

    print(f"\n{'-'*62}")
    print(f"Ошибок: {len(errors)}   Предупреждений: {len(warns)}")
    print(f"{'-'*62}\n")

    if errors:
        print("ОШИБКИ (блокируют передачу в SDD):\n")
        for i in errors:
            loc = f"стр. {i.line}" if i.line else "документ"
            print(f"  [{loc}] {i.message}")
        print()

    if warns:
        print("ПРЕДУПРЕЖДЕНИЯ:\n")
        for i in warns[:40]:
            loc = f"стр. {i.line}" if i.line else "документ"
            print(f"  [{loc}] {i.message}")
        if len(warns) > 40:
            print(f"  ... и ещё {len(warns) - 40}")
        print()

    if not errors and not warns:
        print("  Механических дефектов не найдено.\n")
        print("  Это НЕ означает, что ТЗ корректно по существу:")
        print("  противоречия, пропущенные сценарии и неверные бизнес-правила")
        print("  скрипт не видит. Нужно ревью отдельной сессией.\n")

    return len(errors)


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 check_tz.py <файл-ТЗ> [--strict]")
        sys.exit(2)

    path = sys.argv[1]
    strict = "--strict" in sys.argv

    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"Файл не найден: {path}")
        sys.exit(2)

    issues, blocks = check_document(text)

    # Незаполненный шаблон: много остатков формы и почти нет требований.
    # Блокировать коммит такого файла бессмысленно — работа ещё не начата.
    leftovers = sum(1 for i in issues if "остаток шаблона" in i.message)
    if len(blocks) <= 2 and leftovers >= 2:
        print(f"\n{'='*62}")
        print(f"  {path}")
        print(f"{'='*62}\n")
        print("  Документ ещё не заполнен: это незаполненный шаблон")
        print(f"  ({leftovers} остатков формы, требований: {len(blocks)}).")
        print("  Проверка пропущена.\n")
        sys.exit(0)

    error_count = report(issues, blocks, path)

    if strict and error_count:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()