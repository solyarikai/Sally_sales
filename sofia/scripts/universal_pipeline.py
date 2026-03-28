#!/usr/bin/env python3
"""
Universal Lead Generation Pipeline
====================================
Универсальный pipeline для генерации лидов. Работает с любым проектом —
вся конфигурация (сегменты, тексты, аккаунты) загружается из базы данных.
Ничего не захардкожено под конкретный проект.

Как работает pipeline (простым языком):

  Шаг 0-2:  ПОИСК КОМПАНИЙ — ищем компании через Clay/Apollo по описанию
            идеального клиента (ICP). Убираем дубли и тех, кому уже писали.
  Шаг 3-4:  ФИЛЬТРАЦИЯ И СКРЕЙПИНГ — убираем мусор (офлайн-бизнесы,
            мёртвые сайты). Скачиваем содержимое сайтов для анализа.
  Шаг 5:    КЛАССИФИКАЦИЯ — GPT анализирует сайт каждой компании и решает:
            это наш клиент или нет? Присваивает сегмент и оценку уверенности.
  Шаг 6-8:  ВЕРИФИКАЦИЯ — подготовка к проверке email (оценка стоимости).
  Шаг 9:    ЭКСПОРТ — выгружаем одобренные компании-таргеты из базы.
  Шаг 10:   ИМПОРТ ЛЮДЕЙ — оператор ищет людей (контакты) в Apollo UI,
            экспортирует CSV, скрипт импортирует его.
  Шаг 11:   ПОИСК EMAIL — FindyMail ищет email по LinkedIn профилям.
            Платим только за найденные email ($0.01/шт).
  Шаг 12:   ЗАГРУЗКА В SMARTLEAD — создаём кампанию, привязываем почтовые
            аккаунты, загружаем лиды, загружаем секвенсы (тексты писем),
            устанавливаем расписание. Каждый подшаг требует подтверждения.

  ★ Контрольные точки (Checkpoints):
    CP1 — после blacklist: "Правильный проект? Правильный scope?"
    CP2 — после классификации: "Список компаний корректный?"
    CP3 — перед FindyMail: "Одобряете расходы?"
    Активация — НИКОГДА не запускается автоматически.

Pipeline flow (technical):
  Steps 0-8:  Backend gathering API (Clay/Apollo → Dedup → Blacklist → Scrape → Classify)
  Step 9:     Export targets from DB
  Step 10:    Import Apollo People CSV (manual search results)
  Step 11:    FindyMail email enrichment
  Step 12:    SmartLead upload (with per-step checkpoints)

Input modes:
  --mode natural    : Claude generates filters in conversation, passes as --filters JSON
  --mode structured : Uses CLAY_FILTERS from project config (segment-based)
  --mode lookalike  : Reverse-engineers filters from example company domains
  --mode expand     : Clones a previous run with JSON overrides

Usage:
  # Full pipeline from gathering
  python3 universal_pipeline.py --project-id 42 --mode structured --segment influencer_platforms

  # Resume from Apollo import
  python3 universal_pipeline.py --project-id 42 --from-step people --apollo-csv export.csv

  # Lookalike search
  python3 universal_pipeline.py --project-id 42 --mode lookalike --examples "impact.com,modash.io"

  # Expand previous run to new geography
  python3 universal_pipeline.py --project-id 42 --mode expand --base-run 198 \
    --override '{"country_names": ["Singapore", "Thailand"]}'

  # Dry run
  python3 universal_pipeline.py --project-id 42 --mode structured --segment agencies_mena --dry-run

Env vars: APOLLO_API_KEY, FINDYMAIL_API_KEY, SMARTLEAD_API_KEY
Backend must be running on localhost:8000 (Hetzner)
"""

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx


# ══════════════════════════════════════════════════════════════════════════════
# НАСТРОЙКИ ПОДКЛЮЧЕНИЙ
# Адреса API-сервисов и ключи доступа. Берутся из переменных окружения.
# Перед запуском нужно: set -a && source .env && set +a
# ══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).parent
SOFIA_DIR = SCRIPT_DIR.parent

BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://localhost:8000")
BACKEND_HEADERS = {"X-Company-ID": "1", "Content-Type": "application/json"}

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
APOLLO_BASE = "https://api.apollo.io/api/v1"

FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
FINDYMAIL_BASE = "https://app.findymail.com"
FINDYMAIL_CONCURRENT = 5

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"


# ══════════════════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ ПРОЕКТА
# Загружается из базы данных при запуске. Содержит:
# - Сегменты (кому продаём): названия, должности ЛПР, social proof по регионам
# - Промпт для классификации компаний (GPT решает "наш клиент или нет")
# - Email-аккаунты для отправки писем через SmartLead
# - Расписание отправки (дни недели, время, интервал)
# Чтобы изменить конфигурацию — обновите данные в базе через API,
# скрипт подхватит изменения при следующем запуске.
# ══════════════════════════════════════════════════════════════════════════════

class ProjectConfig:
    """All project-specific configuration, loaded from DB via API."""

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.project_name = ""
        self.segments = {}          # slug → segment data from kb_segments
        self.prompt_id = None       # latest active prompt from gathering_prompts
        self.prompt_text = ""       # fallback prompt text
        self.email_accounts = []    # SmartLead account IDs
        self.schedule = {}          # SmartLead schedule config
        self.state_dir = None       # state directory for this project
        self.csv_dir = None         # output CSV directory

    def load(self):
        """Load all config from backend API."""
        print(f"\n  Loading config for project {self.project_id}...")

        # 1. Project name
        project = api("get", f"/contacts/projects/{self.project_id}", raise_on_error=False)
        self.project_name = project.get("name", f"Project_{self.project_id}")
        print(f"  Project: {self.project_name}")

        # 2. Segments from kb_segments
        segs = api("get", "/knowledge-base/segments", raise_on_error=False)
        seg_list = segs if isinstance(segs, list) else segs.get("items", [])
        for s in seg_list:
            data = s.get("data", {})
            if data.get("project_id") == self.project_id and s.get("is_active", True):
                slug = data.get("slug", s["name"].lower())
                self.segments[slug] = {
                    "id": s["id"],
                    "name": s["name"],
                    **data,
                }
        print(f"  Segments: {', '.join(self.segments.keys()) or 'none'}")

        # 3. Latest prompt from gathering_prompts
        self.prompt_id = get_latest_prompt_id(self.project_id)

        # 4. SmartLead config from project_knowledge
        pk_accounts = api("get", f"/projects/{self.project_id}/knowledge/smartlead/email_accounts",
                          raise_on_error=False)
        if pk_accounts and not pk_accounts.get("_error"):
            val = pk_accounts.get("value", "{}")
            parsed = json.loads(val) if isinstance(val, str) else val
            self.email_accounts = parsed.get("account_ids", [])
        print(f"  Email accounts: {len(self.email_accounts)}")

        pk_config = api("get", f"/projects/{self.project_id}/knowledge/smartlead/config",
                        raise_on_error=False)
        if pk_config and not pk_config.get("_error"):
            val = pk_config.get("value", "{}")
            parsed = json.loads(val) if isinstance(val, str) else val
            self.schedule = parsed.get("schedule", {})

        # 5. State & output directories
        project_slug = self.project_name.replace(" ", "")
        self.state_dir = SOFIA_DIR.parent / "state" / project_slug.lower()
        self.csv_dir = SOFIA_DIR / "output" / project_slug / "pipeline"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        print(f"  State: {self.state_dir}")
        print(f"  Output: {self.csv_dir}")

    def get_segment(self, slug: str) -> dict:
        """Get segment config by slug. Raises if not found."""
        if slug not in self.segments:
            available = ", ".join(self.segments.keys())
            print(f"  ERROR: Segment '{slug}' not found. Available: {available}")
            sys.exit(1)
        return self.segments[slug]

    def get_social_proof(self, country: str, segment_slug: str) -> str:
        """Get social proof text for a country + segment."""
        seg = self.segments.get(segment_slug, {})
        sp = seg.get("social_proof", {})
        return sp.get(country, sp.get("_default", ""))

    def get_titles(self, segment_slug: str) -> list:
        """Get target titles for a segment."""
        seg = self.segments.get(segment_slug, {})
        return seg.get("titles", ["CEO", "Founder", "CTO", "Head of Product"])

    def get_seniorities(self, segment_slug: str) -> list:
        """Get seniorities for Apollo search."""
        seg = self.segments.get(segment_slug, {})
        return seg.get("seniorities", ["owner", "founder", "c_suite", "vp", "head", "director"])

    def get_campaign_name(self, segment_slug: str, contacts: list) -> str:
        """Generate SmartLead campaign name from template."""
        seg = self.segments.get(segment_slug, {})
        template = seg.get("campaign_name_template", "c-{project}_{segment} {geo} #C")

        # Auto-detect geo label
        countries = set(c.get("country", "") for c in contacts if c.get("country"))
        geo = "ALL GEO" if len(countries) > 3 else ", ".join(sorted(countries)).upper()

        display_name = seg.get("display_name", seg.get("name", segment_slug))
        return template.format(project=self.project_name, segment=display_name, geo=geo)

    def validate_email_accounts(self) -> list:
        """Check which SmartLead accounts are still active, update DB."""
        if not self.email_accounts:
            print("  ⚠ No email accounts configured")
            return []

        active = []
        for aid in self.email_accounts:
            try:
                r = httpx.get(f"{SMARTLEAD_BASE}/email-accounts/{aid}",
                              params={"api_key": SMARTLEAD_API_KEY}, timeout=10)
                if r.status_code == 200:
                    details = r.json()
                    is_active = details.get("is_active", True)
                    if is_active:
                        active.append(aid)
                    else:
                        email = details.get("from_email", "?")
                        print(f"  ✗ #{aid} {email} — inactive, skipping")
            except Exception:
                active.append(aid)  # Keep on error — don't remove without confirmation

        if len(active) != len(self.email_accounts):
            print(f"  Active: {len(active)}/{len(self.email_accounts)}")
            # Update in DB
            api("put", f"/projects/{self.project_id}/knowledge/smartlead/email_accounts",
                json={"title": "SmartLead Email Accounts",
                      "value": json.dumps({"account_ids": active,
                                           "updated": datetime.now().strftime('%Y-%m-%d')}),
                      "source": "auto"}, raise_on_error=False)

        self.email_accounts = active
        return active


# ══════════════════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# Работа с файлами (JSON, CSV), загрузка в Google Sheets,
# общение с backend API, сохранение состояния pipeline между запусками.
# ══════════════════════════════════════════════════════════════════════════════

def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def save_csv(path: Path, rows: list[dict], sheet_name: str = None):
    """Save CSV locally and optionally to Google Sheets.
    Naming convention: [PROJECT] | [TYPE] | [SEGMENT] — [DATE]
    """
    if not rows:
        return
    if sheet_name:
        safe_name = sheet_name.replace(" | ", "_").replace(" — ", "_").replace(" ", "_").replace("/", "-")
        path = path.parent / f"{safe_name}.csv"

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → CSV: {path.name} ({len(rows)} rows)")

    if sheet_name:
        _upload_to_sheets(fieldnames, rows, sheet_name)


def _upload_to_sheets(headers: list[str], rows: list[dict], sheet_name: str):
    """Upload data to Google Sheets via backend google_sheets_service."""
    data = [headers] + [[str(row.get(h, "")) for h in headers] for row in rows]
    try:
        import subprocess
        script = (
            'import sys, json, os; sys.path.insert(0, "/app"); os.chdir("/app"); '
            'from app.services.google_sheets_service import google_sheets_service; '
            'data = json.loads(sys.stdin.read()); '
            f'result = google_sheets_service.create_and_populate(title="{sheet_name}", '
            'data=data["data"], share_with=["pn@getsally.io"]); '
            'print(result or "")'
        )
        payload = json.dumps({"data": data})
        result = subprocess.run(
            ["docker", "exec", "-i", "leadgen-backend", "python3", "-c", script],
            input=payload, capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            out = result.stdout.strip()
            sheet_id = out.split("spreadsheets/d/")[1].split("/")[0] if "spreadsheets/d/" in out else out
            print(f"  → Sheet: {sheet_name} — https://docs.google.com/spreadsheets/d/{sheet_id}")
        else:
            print(f"  ⚠ Sheet upload failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠ Sheet upload skipped: {e}")


def normalize_company(name: str) -> str:
    """Clean company name for display."""
    if not name:
        return ""
    for suffix in [" Inc.", " Inc", " LLC", " Ltd.", " Ltd", " GmbH", " AG", " S.A.", " B.V.", " Pty"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def tag() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def api(method: str, path: str, raise_on_error: bool = True, **kwargs) -> dict:
    """Call backend API."""
    url = f"{BACKEND_BASE}/api{path}"
    r = getattr(httpx, method)(url, headers=BACKEND_HEADERS, timeout=300, **kwargs)
    if r.status_code >= 400:
        if raise_on_error:
            print(f"  API ERROR {r.status_code}: {r.text[:500]}")
            sys.exit(1)
        return {"_error": r.status_code, "_detail": r.text[:500]}
    return r.json()


def get_latest_prompt_id(project_id: int) -> int | None:
    """Get the latest active prompt_id for this project from gathering_prompts."""
    result = api("get", f"/pipeline/gathering/prompts?project_id={project_id}", raise_on_error=False)
    prompts = result if isinstance(result, list) else result.get("items", [])
    active = [p for p in prompts if p.get("is_active", True)]
    if active:
        latest = max(active, key=lambda p: p["id"])
        print(f"  Prompt: #{latest['id']} '{latest.get('name', '?')}' "
              f"(usage={latest.get('usage_count', 0)}, avg_target_rate={latest.get('avg_target_rate', '?')})")
        return latest["id"]
    return None


def save_state(state_dir: Path, run_id: int, phase: str, gate_id: int = None, config_key: str = ""):
    save_json(state_dir / "run_state.json",
              {"run_id": run_id, "phase": phase, "gate_id": gate_id,
               "config_key": config_key, "updated_at": ts()})


def load_state(state_dir: Path) -> dict:
    return load_json(state_dir / "run_state.json") or {}


def _checkpoint(message: str) -> bool:
    """Show checkpoint, wait for operator confirmation."""
    print(f"\n  ★ CHECKPOINT: {message}")
    if sys.stdin.isatty():
        print("  [Enter] to continue, [s] to skip, [Ctrl+C] to abort.")
        resp = input("  > ").strip().lower()
        return resp != "s"
    else:
        print("  Non-interactive mode — proceeding.")
        return True


# ══════════════════════════════════════════════════════════════════════════════
# ШАГ 0: ЗАПУСК ПОИСКА КОМПАНИЙ
# Отправляем описание идеального клиента (ICP) в Clay или Apollo.
# Система ищет компании по ключевым словам, индустрии, размеру, географии.
# Результат: список доменов компаний (например thegoatagency.com, modash.io).
# Стоимость: Clay ~$0.01/компания, Apollo бесплатно (через UI эмулятор).
# ══════════════════════════════════════════════════════════════════════════════

def step0_start(config: ProjectConfig, filters: dict, mode: str,
                input_text: str = None, notes: str = "") -> int:
    """Start Clay/Apollo gathering via backend API. Returns run_id."""
    print(f"\n{'='*60}")
    print(f"STEP 0: Start Gathering")
    print(f"  Project: {config.project_name} (ID {config.project_id})")
    print(f"  Mode: {mode}")
    print(f"  Countries: {', '.join(filters.get('country_names', ['global']))}")
    print(f"  Max results: {filters.get('max_results', 5000)}")
    print(f"  ICP: {filters.get('icp_text', '?')[:100]}...")
    print(f"{'='*60}")

    result = api("post", "/pipeline/gathering/start", json={
        "project_id": config.project_id,
        "source_type": "clay.companies.emulator",
        "filters": filters,
        "triggered_by": "operator",
        "input_mode": mode,
        "input_text": input_text,
        "notes": notes,
    })

    run_id = result["id"]
    print(f"\n  Run created: #{run_id}")
    print(f"  Status: {result['status']} / {result['current_phase']}")
    save_state(config.state_dir, run_id, "started", config_key=mode)
    return run_id


# ══════════════════════════════════════════════════════════════════════════════
# ШАГИ 1-8: ОБРАБОТКА КОМПАНИЙ
# Последовательная обработка найденных компаний:
#   Шаг 2 (Blacklist): проверяем, не писали ли мы уже этим компаниям.
#     → CP1: оператор подтверждает проект и список.
#   Шаг 3 (Pre-filter): убираем офлайн-бизнесы, мусорные домены (.gov, .edu).
#   Шаг 4 (Scrape): скачиваем главную страницу сайта каждой компании.
#   Шаг 5 (Analyze): GPT читает сайт и классифицирует компанию —
#     наш сегмент (platform/agency) или нет (OTHER).
#     → CP2: оператор проверяет список таргетов. Убирает ложные срабатывания.
#   Шаг 6 (Verify): подготовка к FindyMail — оценка стоимости.
#     → CP3: оператор одобряет расходы.
# ══════════════════════════════════════════════════════════════════════════════

def step2_blacklist(config: ProjectConfig, run_id: int) -> dict:
    """Run blacklist check → creates CP1 gate."""
    print(f"\n{'='*60}")
    print(f"STEP 2: Blacklist Check (run #{run_id})")
    print(f"{'='*60}")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/blacklist-check")
    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        gate_id = gate["id"]
        scope = gate.get("scope", {})
        save_state(config.state_dir, run_id, "awaiting_scope_ok", gate_id=gate_id)
        print(f"\n  ★ CHECKPOINT 1 — gate #{gate_id}")
        print(f"  Passed: {scope.get('passed', '?')}, Rejected: {scope.get('rejected', '?')}")
        return {"gate_id": gate_id, "scope": scope}
    return {}


def approve_gate(gate_id: int, note: str = "Approved") -> dict:
    """Approve a checkpoint gate."""
    result = api("post", f"/pipeline/gathering/approval-gates/{gate_id}/approve",
                 json={"decision_note": note})
    print(f"  Gate #{gate_id} approved → {result.get('new_phase', '?')}")
    return result


def step3_prefilter(run_id: int) -> dict:
    print(f"\n  Step 3: Pre-filter (run #{run_id})")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/pre-filter")
    print(f"  Passed: {result.get('passed', '?')}")
    return result


def step4_scrape(run_id: int) -> dict:
    print(f"\n  Step 4: Scrape websites (run #{run_id}) — may take a few minutes...")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/scrape")
    print(f"  Scraped: {result.get('scraped', '?')}, Skipped: {result.get('skipped', '?')}")
    return result


def step5_analyze(config: ProjectConfig, run_id: int, prompt_text: str = None) -> dict:
    """Run GPT classification. Uses prompt_id from DB by default."""
    print(f"\n  Step 5: Analyze (run #{run_id})")
    params = {"model": "gpt-4o-mini"}
    if config.prompt_id:
        params["prompt_id"] = config.prompt_id
        print(f"  Prompt ID: {config.prompt_id}")
    elif prompt_text:
        params["prompt_text"] = prompt_text
        print(f"  Prompt: {prompt_text[:80]}...")

    result = api("post", f"/pipeline/gathering/runs/{run_id}/analyze", params=params)
    targets = result.get("targets_found", 0)
    total = result.get("total_analyzed", 0)
    print(f"  Targets: {targets}/{total} ({targets/total*100:.0f}%)" if total else "  No companies analyzed")

    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        save_state(config.state_dir, run_id, "awaiting_targets_ok", gate_id=gate["id"])
        print(f"\n  ★ CHECKPOINT 2 — gate #{gate['id']}")
        target_list = gate.get("scope", {}).get("targets", [])
        if isinstance(target_list, list):
            for t in target_list:
                print(f"    {t.get('domain','?')} — {t.get('name','?')} "
                      f"({t.get('segment','?')} {t.get('confidence','?')})")
        return {"gate_id": gate["id"], "targets_found": targets, "total_analyzed": total}
    return {"targets_found": targets, "total_analyzed": total}


def step6_prepare_verify(run_id: int) -> dict:
    """Prepare FindyMail verification → creates CP3 with cost estimate."""
    print(f"\n  Step 6: Prepare Verification (run #{run_id})")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/prepare-verification")
    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        scope = gate.get("scope", {})
        print(f"\n  ★ CHECKPOINT 3 — gate #{gate['id']}")
        print(f"  Emails to verify: {scope.get('emails_to_verify', '?')}")
        print(f"  Estimated cost: ${scope.get('estimated_cost_usd', '?')}")
        return {"gate_id": gate["id"], "scope": scope}
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ШАГ 9: ЭКСПОРТ КОМПАНИЙ-ТАРГЕТОВ
# Выгружаем из базы все компании, прошедшие классификацию (is_target=true).
# Разбиваем по сегментам, сохраняем CSV локально и в Google Sheets.
# Эти компании — основа для поиска людей (контактов) на следующем шаге.
# ══════════════════════════════════════════════════════════════════════════════

def step9_export_targets(config: ProjectConfig, force: bool = False) -> list[dict]:
    """Export approved target companies from backend DB."""
    targets_file = config.state_dir / "targets.json"
    print(f"\n{'='*60}")
    print(f"STEP 9: Export Targets (project_id={config.project_id})")
    print(f"{'='*60}")

    if targets_file.exists() and not force:
        targets = load_json(targets_file)
        print(f"  Loaded from cache: {len(targets)} targets")
        return targets

    # Export via psql
    import subprocess
    sql = (f"SELECT domain, name, matched_segment, confidence "
           f"FROM discovered_companies WHERE project_id={config.project_id} AND is_target=true")
    r = subprocess.run(
        ["docker", "exec", "leadgen-postgres", "psql", "-U", "leadgen",
         "-d", "leadgen", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, timeout=30,
    )

    targets = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            targets.append({
                "domain": parts[0].strip(),
                "company_name": parts[1].strip(),
                "segment": parts[2].strip(),
                "confidence": parts[3].strip() if len(parts) > 3 else "",
            })

    if not targets:
        print("  No targets found. Complete backend pipeline first (Steps 0-8).")
        sys.exit(1)

    save_json(targets_file, targets)

    # Per-segment stats & CSV export
    today = tag()
    by_seg = {}
    for t in targets:
        seg = t.get("segment", "UNKNOWN")
        by_seg.setdefault(seg, []).append(t)

    print(f"  Exported: {len(targets)} targets")
    for seg_name, seg_targets in sorted(by_seg.items()):
        # Find segment code from config
        seg_code = seg_name
        for slug, seg_data in config.segments.items():
            if seg_data["name"] == seg_name:
                seg_code = seg_data.get("segment_code", seg_name)
                break
        code = config.project_name[:2].upper()
        sheet_name = f"{code} | Targets | {seg_code} — {today}"
        save_csv(config.csv_dir / f"targets_{seg_code}_{today}.csv", seg_targets, sheet_name=sheet_name)
        print(f"    {seg_name}: {len(seg_targets)}")

    return targets


# ══════════════════════════════════════════════════════════════════════════════
# ШАГ 10: ИМПОРТ КОНТАКТОВ ИЗ APOLLO
# Оператор вручную ищет людей (ЛПР) в Apollo People UI по списку компаний
# из шага 9. Экспортирует результат как CSV. Этот шаг импортирует CSV:
# - Маппит колонки Apollo → наш формат (имя, должность, LinkedIn, компания)
# - Подтягивает domain из базы таргетов (чтобы связать человека с компанией)
# - Назначает social_proof по стране человека (для персонализации писем)
# - Убирает дубли по LinkedIn URL
# Результат: список людей с LinkedIn, готовых к поиску email.
# ══════════════════════════════════════════════════════════════════════════════

APOLLO_CSV_COLUMNS = {
    "first_name": ["First Name", "first_name"],
    "last_name": ["Last Name", "last_name"],
    "email": ["Email", "email", "Email Address"],
    "title": ["Title", "title", "Job Title"],
    "company_name": ["Company", "company", "Company Name", "Organization Name"],
    "domain": ["Website", "website", "Company Domain", "domain", "Domain"],
    "linkedin_url": ["Person Linkedin Url", "LinkedIn URL", "linkedin_url", "LinkedIn", "Person LinkedIn URL"],
    "country": ["Country", "country", "Person Country"],
    "employees": ["# Employees", "employees", "Number of Employees", "Company Size"],
}


def _normalize_domain(raw: str) -> str:
    d = raw.strip().lower()
    for prefix in ["https://", "http://", "www."]:
        if d.startswith(prefix):
            d = d[len(prefix):]
    d = d.rstrip("/").split("/")[0]
    return d


def _map_csv_row(row: dict, targets_by_domain: dict, config: ProjectConfig = None) -> dict:
    """Map an Apollo CSV row to our contact format."""
    def _get(field: str) -> str:
        for col in APOLLO_CSV_COLUMNS.get(field, [field]):
            if col in row and row[col]:
                return row[col].strip()
        return ""

    domain = _normalize_domain(_get("domain") or (_get("email").split("@")[-1] if "@" in _get("email") else ""))
    target = targets_by_domain.get(domain, {})
    segment = target.get("segment", target.get("analysis_segment", "UNKNOWN"))

    # Find segment slug for social_proof lookup
    seg_slug = ""
    if config:
        for slug, seg_data in config.segments.items():
            if seg_data["name"] == segment:
                seg_slug = slug
                break

    country = _get("country") or target.get("country", "")
    social_proof = config.get_social_proof(country, seg_slug) if config and seg_slug else ""

    return {
        "first_name": _get("first_name"),
        "last_name": _get("last_name"),
        "email": _get("email"),
        "title": _get("title"),
        "company_name": normalize_company(_get("company_name") or target.get("company_name", domain)),
        "domain": domain,
        "segment": segment,
        "linkedin_url": _get("linkedin_url"),
        "country": country,
        "employees": _get("employees") or target.get("employees", ""),
        "social_proof": social_proof,
    }


def step10_import_apollo_csv(config: ProjectConfig, csv_path: str, targets: list[dict],
                              force: bool = False, segment_override: str = None) -> list[dict]:
    """Import contacts from a manual Apollo People Search CSV export."""
    contacts_file = config.state_dir / "contacts.json"
    print(f"\n{'='*60}")
    seg_label = f" ({segment_override})" if segment_override else ""
    print(f"STEP 10: Import Apollo People CSV{seg_label}")
    print(f"{'='*60}")

    if contacts_file.exists() and not force:
        contacts = load_json(contacts_file)
        print(f"  Loaded from cache: {len(contacts)} contacts")
        return contacts

    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"  ERROR: CSV not found: {csv_path}")
        sys.exit(1)

    targets_by_domain = {t.get("domain", "").strip().lower(): t for t in targets if t.get("domain")}

    with csv_file.open("r", encoding="utf-8-sig") as f:
        raw_rows = list(csv.DictReader(f))
    print(f"  CSV rows: {len(raw_rows)}")
    if raw_rows:
        print(f"  Columns: {', '.join(raw_rows[0].keys())}")

    all_contacts = []
    skipped_no_name = skipped_no_domain = 0
    for row in raw_rows:
        contact = _map_csv_row(row, targets_by_domain, config)
        if segment_override:
            # Find slug for override segment
            seg_slug = ""
            for slug, seg_data in config.segments.items():
                if seg_data["name"] == segment_override:
                    seg_slug = slug
                    break
            contact["segment"] = segment_override
            contact["social_proof"] = config.get_social_proof(contact["country"], seg_slug)
        if not contact["first_name"]:
            skipped_no_name += 1
            continue
        if not contact["domain"]:
            skipped_no_domain += 1
            continue
        all_contacts.append(contact)

    # Dedupe by linkedin_url or (first_name + last_name + domain)
    seen = set()
    deduped = []
    for c in all_contacts:
        key = c["linkedin_url"] or f"{c['first_name']}|{c['last_name']}|{c['domain']}"
        if key not in seen:
            seen.add(key)
            deduped.append(c)
    all_contacts = deduped

    save_json(contacts_file, all_contacts)

    with_email = sum(1 for c in all_contacts if c["email"])
    with_li = sum(1 for c in all_contacts if c["linkedin_url"])
    segments = Counter(c["segment"] for c in all_contacts)

    print(f"\n  Imported: {len(all_contacts)} contacts")
    print(f"  With email: {with_email}, with LinkedIn: {with_li}")
    if skipped_no_name: print(f"  Skipped (no name): {skipped_no_name}")
    if skipped_no_domain: print(f"  Skipped (no domain): {skipped_no_domain}")
    print(f"  Segments: {dict(segments)}")

    # Save import CSV + Google Sheet
    today = tag()
    code = config.project_name[:2].upper()
    save_csv(config.csv_dir / f"import_apollo_{today}.csv", all_contacts,
             sheet_name=f"{code} | Import | Apollo People — {today}")

    return all_contacts


# ══════════════════════════════════════════════════════════════════════════════
# ШАГ 11: ПОИСК EMAIL ЧЕРЕЗ FINDYMAIL
# Для каждого человека с LinkedIn URL — FindyMail ищет рабочий email.
# Оплата: $0.01 за каждый НАЙДЕННЫЙ email. Ненайденные — бесплатно.
# Типичный hit rate: 60-80% (из 500 LinkedIn → ~350-400 email).
# Результат: два файла —
#   1) "Verified Emails" — люди с email, готовы к отправке в SmartLead
#   2) "No Email (LinkedIn only)" — люди без email, можно работать через LinkedIn
# Оба сохраняются локально и в Google Sheets.
# ══════════════════════════════════════════════════════════════════════════════

async def find_email(client: httpx.AsyncClient, linkedin_url: str) -> dict:
    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        r = await client.post(
            f"{FINDYMAIL_BASE}/api/search/linkedin",
            headers={"Authorization": f"Bearer {FINDYMAIL_API_KEY}", "Content-Type": "application/json"},
            json={"linkedin_url": url}, timeout=60.0,
        )
        if r.status_code == 200:
            data = r.json()
            contact = data.get("contact", {})
            return {"email": data.get("email") or contact.get("email") or "",
                    "verified": data.get("verified", False) or contact.get("verified", False)}
        elif r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return {"email": "", "verified": False}
    except RuntimeError:
        raise
    except Exception:
        return {"email": "", "verified": False}


async def step11_findymail(config: ProjectConfig, contacts: list[dict],
                            max_contacts: int = 1500, force: bool = False) -> list[dict]:
    """FindyMail enrichment. Charges only for found emails."""
    enriched_file = config.state_dir / "enriched.json"
    progress_file = config.state_dir / "findymail_progress.json"

    print(f"\n{'='*60}")
    print(f"STEP 11: FindyMail Enrichment")
    print(f"{'='*60}")

    if enriched_file.exists() and not force:
        return load_json(enriched_file)

    if not FINDYMAIL_API_KEY:
        print("  ERROR: FINDYMAIL_API_KEY not set")
        sys.exit(1)

    already_have = [c for c in contacts if c.get("email")]
    to_enrich = [c for c in contacts if not c.get("email") and c.get("linkedin_url")]
    to_enrich = to_enrich[:max_contacts]

    print(f"  {len(already_have)} already have email")
    print(f"  {len(to_enrich)} to enrich (charged per found email only)")
    print(f"\n  ★ CHECKPOINT: Enrich {len(to_enrich)} contacts via FindyMail?")
    if sys.stdin.isatty():
        print("  Enter to continue, Ctrl+C to abort.")
        input()
    else:
        print("  Non-interactive mode — proceeding.")

    done = load_json(progress_file) or {}
    found = not_found = 0
    out_of_credits = False
    t0 = time.time()
    sem = asyncio.Semaphore(FINDYMAIL_CONCURRENT)

    async def process_one(row):
        nonlocal found, not_found, out_of_credits
        if out_of_credits:
            return
        li = row.get("linkedin_url", "").strip()
        if not li:
            return
        if li in done:
            row["email"] = done[li].get("email", "")
            if done[li].get("email"): found += 1
            else: not_found += 1
            return
        async with sem:
            async with httpx.AsyncClient() as client:
                try:
                    res = await find_email(client, li)
                except RuntimeError:
                    out_of_credits = True
                    return
            row["email"] = res.get("email", "")
            done[li] = res
            if res.get("email"):
                found += 1
                print(f"  ✓ {row.get('first_name','')} {row.get('last_name','')} → {res['email']}")
            else:
                not_found += 1

    for i in range(0, len(to_enrich), 20):
        if out_of_credits:
            print("\n  OUT OF CREDITS")
            break
        await asyncio.gather(*[process_one(r) for r in to_enrich[i:i+20]])
        save_json(progress_file, done)

    all_enriched = already_have + to_enrich
    save_json(enriched_file, all_enriched)

    with_email = [c for c in all_enriched if c.get("email", "").strip()]
    without_email = [c for c in all_enriched if not c.get("email") and c.get("linkedin_url")]

    # Save split files + Google Sheets
    today = tag()
    code = config.project_name[:2].upper()
    save_csv(config.csv_dir / f"leads_verified_{today}.csv", with_email,
             sheet_name=f"{code} | Leads | Verified Emails — {today}")
    save_csv(config.csv_dir / f"leads_no_email_{today}.csv", without_email,
             sheet_name=f"{code} | Leads | No Email (LinkedIn only) — {today}")

    cost = len(with_email) * 0.01
    print(f"\n  Done in {time.time()-t0:.0f}s. With email: {len(with_email)}, without: {len(without_email)}")
    print(f"  FindyMail cost: ${cost:.2f} ({len(with_email)} credits, charged per found email only)")
    return all_enriched


# ══════════════════════════════════════════════════════════════════════════════
# GOD_SEQUENCE — АВТОГЕНЕРАЦИЯ ТЕКСТОВ ПИСЕМ
# Если для сегмента нет готовых текстов (markdown файл), система сама
# генерирует 5-шаговую email-секвенцию через GPT-4o, используя:
#   - ICP проекта (кто наш клиент, что болит)
#   - Описание продукта (что продаём)
#   - Стиль коммуникации (как пишем)
#   - Данные сегмента (должности ЛПР, примеры компаний)
# Оператор обязательно проверяет сгенерированные тексты перед загрузкой.
# Приоритет: написанные человеком тексты (markdown) > автогенерация (GPT-4o).
# ══════════════════════════════════════════════════════════════════════════════

def god_sequence(config: ProjectConfig, segment_slug: str) -> list[dict] | None:
    """Generate email sequence from project knowledge using GPT-4o.
    Returns list of steps [{subject, body, label}] or None on failure.
    Operator reviews before upload to SmartLead.
    """
    print(f"\n{'='*60}")
    print(f"GOD_SEQUENCE: Generating emails for {segment_slug}")
    print(f"{'='*60}")

    seg = config.get_segment(segment_slug)

    # Gather context from project_knowledge
    pk_icp = api("get", f"/projects/{config.project_id}/knowledge/icp", raise_on_error=False)
    pk_outreach = api("get", f"/projects/{config.project_id}/knowledge/outreach", raise_on_error=False)
    pk_notes = api("get", f"/projects/{config.project_id}/knowledge/notes", raise_on_error=False)

    icp_context = ""
    if isinstance(pk_icp, list):
        for item in pk_icp:
            icp_context += f"\n{item.get('title','')}: {item.get('value','')}\n"
    elif isinstance(pk_icp, dict) and not pk_icp.get("_error"):
        icp_context = str(pk_icp.get("value", ""))

    outreach_context = ""
    if isinstance(pk_outreach, list):
        for item in pk_outreach:
            outreach_context += f"\n{item.get('title','')}: {item.get('value','')}\n"

    product_context = ""
    if isinstance(pk_notes, list):
        for item in pk_notes:
            product_context += f"\n{item.get('title','')}: {item.get('value','')}\n"

    # Build GPT-4o prompt
    prompt = f"""Generate a 5-step cold email sequence for B2B outreach.

PROJECT: {config.project_name}
SEGMENT: {seg.get('display_name', segment_slug)}
SEGMENT DESCRIPTION: {seg.get('description', '')}
TARGET TITLES: {', '.join(seg.get('titles', []))}
SOCIAL PROOF VARIABLE: {{{{social_proof}}}} (will be replaced per recipient's region)
COMPANY NAME VARIABLE: {{{{company_name}}}}
FIRST NAME VARIABLE: {{{{first_name}}}}

ICP CONTEXT:
{icp_context}

PRODUCT:
{product_context}

OUTREACH STYLE:
{outreach_context}

RULES:
- 50-75 words per email (optimal for cold email)
- Pain-based messaging, NOT feature-dump
- Email 1: JTBD question (what job does the prospect need done?)
- Email 2: Case study or tangible offer
- Email 3: New angle (stat + social proof)
- Email 4: Competitive differentiation
- Email 5: Break-up + redirect to right person
- Steps 1 and 2: create A and B variants (test different angles)
- Steps 3-5: single version
- Sign off as sender from the project
- Use {{{{social_proof}}}}, {{{{company_name}}}}, {{{{first_name}}}} variables
- Plain text only, no HTML, no links except calendar link in email 4

OUTPUT FORMAT (JSON array):
[
  {{"label": "1A", "subject": "...", "body": "..."}},
  {{"label": "1B", "subject": "...", "body": "..."}},
  {{"label": "2A", "subject": "...", "body": "..."}},
  {{"label": "2B", "subject": "...", "body": "..."}},
  {{"label": "3", "subject": "...", "body": "..."}},
  {{"label": "4", "subject": "...", "body": "..."}},
  {{"label": "5", "subject": "...", "body": "..."}}
]
Return ONLY the JSON array, no explanation."""

    # Call GPT-4o via backend
    try:
        import subprocess
        script = (
            'import sys, json, os; sys.path.insert(0, "/app"); os.chdir("/app"); '
            'from openai import OpenAI; '
            'client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")); '
            'prompt = json.loads(sys.stdin.read())["prompt"]; '
            'r = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":prompt}], '
            'temperature=0.7, max_tokens=4000); '
            'print(r.choices[0].message.content)'
        )
        payload = json.dumps({"prompt": prompt})
        result = subprocess.run(
            ["docker", "exec", "-i", "leadgen-backend", "python3", "-c", script],
            input=payload, capture_output=True, text=True, timeout=120,
        )

        if result.returncode != 0:
            print(f"  ⚠ GPT-4o error: {result.stderr[:300]}")
            return None

        # Parse JSON from response
        raw = result.stdout.strip()
        # Handle markdown code blocks
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        steps = json.loads(raw)
        print(f"  Generated {len(steps)} email steps:")
        for s in steps:
            print(f"    {s['label']}: {s['subject'][:50]}...")

        return steps

    except Exception as e:
        print(f"  ⚠ GOD_SEQUENCE failed: {e}")
        return None


def load_sequences_from_file(config: ProjectConfig, segment_slug: str) -> list[dict] | None:
    """Load sequences from markdown file (higher priority than GOD_SEQUENCE)."""
    seg = config.get_segment(segment_slug)
    seq_file_path = seg.get("sequence_file", "")
    if not seq_file_path:
        return None

    # Try relative to repo root
    for base in [SOFIA_DIR.parent, SOFIA_DIR, Path(".")]:
        full_path = base / seq_file_path
        if full_path.exists():
            text = full_path.read_text(encoding="utf-8")
            steps = []
            pattern = re.compile(
                r'## Email (\d+[AB]?) .+?\n\n\*\*Subject:\*\* (.+?)\n\n(.*?)(?=\n---|\n## |\Z)',
                re.DOTALL
            )
            for m in pattern.finditer(text):
                label, subject, body = m.group(1), m.group(2), m.group(3).strip()
                body = re.sub(r'\n`\d+ words`', '', body).strip()
                steps.append({"label": label, "subject": subject, "body": body})
            if steps:
                print(f"  Loaded {len(steps)} steps from {full_path.name}")
                return steps
    return None


def get_sequences(config: ProjectConfig, segment_slug: str) -> list[dict] | None:
    """Get sequences: markdown file first, GOD_SEQUENCE as fallback."""
    # Priority 1: markdown file (written by human)
    steps = load_sequences_from_file(config, segment_slug)
    if steps:
        return steps

    # Priority 2: GOD_SEQUENCE (auto-generated)
    print(f"  No sequence file found — generating via GOD_SEQUENCE...")
    steps = god_sequence(config, segment_slug)
    if steps and _checkpoint("Review generated sequence above. Approve?"):
        # Save generated sequence as markdown for future use
        today = tag()
        out_path = config.csv_dir / f"generated_sequence_{segment_slug}_{today}.md"
        with out_path.open("w") as f:
            for s in steps:
                f.write(f"## Email {s['label']}\n\n**Subject:** {s['subject']}\n\n{s['body']}\n\n---\n\n")
        print(f"  Saved to {out_path.name}")
        return steps

    return None


# ══════════════════════════════════════════════════════════════════════════════
# ШАГ 12: ЗАГРУЗКА В SMARTLEAD (с подтверждением каждого подшага)
# Финальный шаг — подготовка и запуск email-кампании. Подшаги:
#   12a: Проверка social_proof — показывает распределение по регионам.
#        "187 лидов: 50 UK, 40 India, 30 MENA..." — оператор проверяет.
#   12b: Создание кампании — `c-ProjectName_Segment ALL GEO #C`
#   12c: Привязка email-аккаунтов — проверяет какие аккаунты активны.
#   12d: Загрузка лидов — email, имя, компания, social_proof (переменная).
#   12e: Загрузка секвенсов — 5 писем, шаги 1-2 с A/B вариантами.
#        ⚠ SmartLead API не поддерживает A/B — B варианты добавлять вручную.
#   12f: Установка расписания — дни, время, интервал между письмами.
#   12g: Активация — ТОЛЬКО с ручным подтверждением. НИКОГДА автоматически.
#        Это точка невозврата — после активации начинается отправка писем.
# ══════════════════════════════════════════════════════════════════════════════

def sl_params():
    return {"api_key": SMARTLEAD_API_KEY}


def create_campaign(name: str) -> int:
    r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/create", params=sl_params(), json={
        "name": name,
    }, timeout=30)
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"  Created campaign: {cid} — {name}")
    return cid


def upload_leads(campaign_id: int, contacts: list[dict]) -> int:
    leads = []
    for c in contacts:
        leads.append({
            "email": c["email"].strip(),
            "first_name": c.get("first_name", ""),
            "last_name": c.get("last_name", ""),
            "company_name": normalize_company(c.get("company_name", "")),
            "linkedin_profile": c.get("linkedin_url", ""),
            "custom_fields": {
                "social_proof": c.get("social_proof", ""),
                "title": c.get("title", ""),
                "country": c.get("country", ""),
                "segment": c.get("segment", ""),
            },
        })
    total = 0
    for i in range(0, len(leads), 100):
        batch = leads[i:i+100]
        r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/leads", params=sl_params(),
                       json={"lead_list": batch}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            uploaded = data.get("upload_count", len(batch))
            total += uploaded
            blocked = data.get("block_count", 0)
            dupes = data.get("duplicate_count", 0)
            if blocked or dupes:
                print(f"    Batch: +{uploaded}, blocked={blocked}, dupes={dupes}")
        elif r.status_code == 429:
            time.sleep(70)
            r2 = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/leads", params=sl_params(),
                            json={"lead_list": batch}, timeout=60)
            if r2.status_code == 200:
                total += r2.json().get("upload_count", len(batch))
        else:
            print(f"    Upload error: {r.status_code} {r.text[:200]}")
        time.sleep(1)
    print(f"  Uploaded: {total}/{len(leads)}")
    return total


def _show_social_proof_stats(contacts: list[dict], segment: str):
    """Show social_proof distribution for validation before upload."""
    sp_counts = Counter(c.get("social_proof", "NO_PROOF") for c in contacts)
    country_counts = Counter(c.get("country", "UNKNOWN") for c in contacts)
    print(f"\n  Social proof distribution ({segment}):")
    for sp, cnt in sp_counts.most_common():
        print(f"    {cnt:3d}  {sp}")
    print(f"  Top countries:")
    for co, cnt in country_counts.most_common(8):
        print(f"    {cnt:3d}  {co}")


def step12_upload(config: ProjectConfig, contacts: list[dict]):
    """SmartLead upload with checkpoints at every step."""
    print(f"\n{'='*60}")
    print(f"STEP 12: SmartLead Upload")
    print(f"{'='*60}")

    if not SMARTLEAD_API_KEY:
        print("  ERROR: SMARTLEAD_API_KEY not set")
        sys.exit(1)

    # Dedup by email
    with_email = [c for c in contacts if c.get("email", "").strip()]
    seen = set()
    deduped = []
    for c in with_email:
        e = c["email"].strip().lower()
        if e not in seen:
            seen.add(e)
            deduped.append(c)

    # Group by segment
    by_segment = {}
    for c in deduped:
        seg = c.get("segment", "UNKNOWN")
        by_segment.setdefault(seg, []).append(c)

    upload_log = load_json(config.state_dir / "upload_log.json") or {}
    TIMING = [0, 4, 4, 6, 7]

    for seg_name, seg_contacts in sorted(by_segment.items()):
        # Find segment slug
        seg_slug = ""
        for slug, seg_data in config.segments.items():
            if seg_data["name"] == seg_name:
                seg_slug = slug
                break

        campaign_name = config.get_campaign_name(seg_slug or seg_name, seg_contacts)
        print(f"\n{'─'*50}")
        print(f"  Campaign: {campaign_name} ({len(seg_contacts)} leads)")
        print(f"{'─'*50}")

        # ── Social proof validation ──
        _show_social_proof_stats(seg_contacts, seg_name)
        if not _checkpoint(f"Social proof distribution OK for '{campaign_name}'?"):
            print("  Skipping this segment.")
            continue

        # ── 12a: Create campaign ──
        cid = upload_log.get(seg_name, {}).get("campaign_id")
        if cid:
            print(f"  Campaign already exists: {cid}")
        else:
            if not _checkpoint(f"Create campaign '{campaign_name}'?"):
                continue
            cid = create_campaign(campaign_name)
            upload_log[seg_name] = {"campaign_id": cid, "campaign_name": campaign_name, "at": ts()}
            save_json(config.state_dir / "upload_log.json", upload_log)

        # ── 12b: Validate & attach email accounts ──
        if not _checkpoint(f"Attach email accounts to '{campaign_name}'?"):
            print("  Skipping email accounts.")
        else:
            active_accounts = config.validate_email_accounts()
            if active_accounts:
                r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/email-accounts", params=sl_params(),
                               json={"email_account_ids": active_accounts}, timeout=30)
                if r.status_code == 200:
                    print(f"  Attached {len(active_accounts)} email accounts")
                else:
                    print(f"  ⚠ Email accounts error: {r.status_code} {r.text[:200]}")

        # ── 12c: Upload leads ──
        if not _checkpoint(f"Upload {len(seg_contacts)} leads to '{campaign_name}'?"):
            print("  Skipping leads upload.")
        else:
            uploaded = upload_leads(cid, seg_contacts)
            upload_log[seg_name]["leads"] = uploaded
            upload_log[seg_name]["uploaded_at"] = ts()
            save_json(config.state_dir / "upload_log.json", upload_log)

        # ── 12d: Load and upload sequences ──
        sequences = get_sequences(config, seg_slug) if seg_slug else None
        if sequences:
            if not _checkpoint(f"Upload {len(sequences)} email steps to '{campaign_name}'?"):
                print("  Skipping sequences.")
            else:
                # Group A/B variants
                step_groups = {}
                for s in sequences:
                    step_num = re.match(r'(\d+)', s["label"]).group(1)
                    step_groups.setdefault(step_num, []).append(s)

                # Upload all steps at once (variant A only — API limitation)
                seq_payload = []
                for i, (num, variants) in enumerate(sorted(step_groups.items())):
                    wait_days = TIMING[i] if i < len(TIMING) else 7
                    seq_payload.append({
                        "seq_number": i + 1,
                        "seq_delay_details": {"delay_in_days": wait_days},
                        "subject": variants[0]["subject"],
                        "email_body": variants[0]["body"],
                    })

                r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/sequences",
                               params=sl_params(), json={"sequences": seq_payload}, timeout=30)
                if r.status_code == 200:
                    print(f"  Sequences uploaded ({len(seq_payload)} steps)")
                    # Report B variants that need manual add
                    for num, variants in sorted(step_groups.items()):
                        if len(variants) > 1:
                            print(f"    ⚠ Step {num} B variant — add manually in SmartLead UI")
                            print(f"      Subject: {variants[1]['subject']}")
                else:
                    print(f"  ⚠ Sequences error: {r.status_code} {r.text[:200]}")

                upload_log[seg_name]["sequences_uploaded"] = True
                save_json(config.state_dir / "upload_log.json", upload_log)
        else:
            print("  ⚠ No sequences — add manually in SmartLead UI.")

        # ── 12e: Set schedule ──
        if config.schedule:
            if not _checkpoint(f"Set schedule for '{campaign_name}'?"):
                print("  Skipping schedule.")
            else:
                r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/schedule",
                               params=sl_params(), json=config.schedule, timeout=30)
                if r.status_code == 200:
                    tz = config.schedule.get("timezone", "?")
                    start = config.schedule.get("start_hour", "?")
                    end = config.schedule.get("end_hour", "?")
                    print(f"  Schedule set: {start}-{end} {tz}")
                else:
                    print(f"  ⚠ Schedule error: {r.status_code} {r.text[:200]}")

        # ── 12f: Активация — ТОЛЬКО вручную в SmartLead UI ──
        # Скрипт НИКОГДА не активирует кампанию. Это делает оператор
        # в SmartLead после финальной проверки всех настроек.
        print(f"\n  ✓ Campaign '{campaign_name}' готова в DRAFTED статусе.")
        print(f"  → Активируйте вручную в SmartLead UI после проверки.")

    # Final summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    for seg, info in upload_log.items():
        seqs = "✅" if info.get("sequences_uploaded") else "❌"
        print(f"    {info.get('campaign_name', seg)}: {info.get('leads', 0)} leads, sequences={seqs}")
    print(f"{'='*60}")


# ══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 3: ПОИСК ПОХОЖИХ КОМПАНИЙ (LOOKALIKE)
# Даёшь примеры хороших клиентов (домены) → система анализирует их
# общие черты (индустрия, размер, страна) → генерирует фильтры для поиска
# похожих компаний. Пример: "найди компании похожие на impact.com и modash.io"
# ══════════════════════════════════════════════════════════════════════════════

def mode3_lookalike(config: ProjectConfig, examples: list[str]) -> dict:
    """Build Clay filters by analyzing example companies from DB."""
    print(f"\n{'='*60}")
    print(f"MODE 3: Lookalike — {len(examples)} examples")
    print(f"{'='*60}")

    import subprocess
    domains_sql = "','".join(d.strip().lower() for d in examples)
    sql = (f"SELECT domain, name, matched_segment, country, employee_count "
           f"FROM discovered_companies WHERE project_id={config.project_id} "
           f"AND lower(domain) IN ('{domains_sql}')")
    r = subprocess.run(
        ["docker", "exec", "leadgen-postgres", "psql", "-U", "leadgen",
         "-d", "leadgen", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, timeout=15,
    )

    companies = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip(): continue
        parts = line.split("|")
        if len(parts) >= 3:
            companies.append({
                "domain": parts[0].strip(), "name": parts[1].strip(),
                "segment": parts[2].strip(),
                "country": parts[3].strip() if len(parts) > 3 else "",
                "employees": parts[4].strip() if len(parts) > 4 else "",
            })

    missing = [d for d in examples if d.strip().lower() not in {c["domain"].lower() for c in companies}]
    if missing:
        print(f"  ⚠ Not in DB: {', '.join(missing)}")
    if not companies:
        print("  ERROR: No examples found in DB")
        sys.exit(1)

    # Extract patterns
    segments = Counter(c["segment"] for c in companies if c["segment"])
    countries = Counter(c["country"] for c in companies if c["country"])
    dominant_segment = segments.most_common(1)[0][0] if segments else "INFLUENCER_PLATFORMS"
    top_countries = [c for c, _ in countries.most_common(5)] if countries else []

    emp_values = [int(c["employees"]) for c in companies if c["employees"].isdigit()]
    min_emp = min(emp_values) // 2 if emp_values else 5
    max_emp = max(emp_values) * 2 if emp_values else 5000

    example_names = ", ".join(c["name"] for c in companies[:5])
    icp_text = (
        f"Companies similar to: {example_names}. "
        f"Find companies in the same space — similar products, services, size, and market. "
        f"Industry focus: {dominant_segment.replace('_', ' ').lower()}. "
    )

    filters = {
        "icp_text": icp_text,
        "industries": ["Computer Software", "Internet", "Marketing and Advertising",
                        "Information Technology and Services", "Online Media"],
        "minimum_member_count": max(min_emp, 5),
        "maximum_member_count": min(max_emp, 5000),
        "max_results": 5000,
    }
    if top_countries:
        filters["country_names"] = top_countries

    print(f"  Segment: {dominant_segment}")
    print(f"  Countries: {', '.join(top_countries) if top_countries else 'global'}")
    print(f"  Employees: {filters['minimum_member_count']}-{filters['maximum_member_count']}")
    return {"segment": dominant_segment, "filters": filters}


# ══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 4: РАСШИРЕНИЕ ПРЕДЫДУЩЕГО ПОИСКА (EXPAND)
# Берёт фильтры из предыдущего рана и запускает с изменениями.
# Пример: "тот же поиск что run #198, но для Singapore вместо Dubai"
# Удобно для масштабирования удачных поисков на новые регионы.
# ══════════════════════════════════════════════════════════════════════════════

def mode4_expand(base_run_id: int, overrides: dict) -> dict:
    """Clone filters from an existing run, apply JSON overrides."""
    print(f"\n{'='*60}")
    print(f"MODE 4: Expand — base run #{base_run_id}")
    print(f"{'='*60}")

    run = api("get", f"/pipeline/gathering/runs/{base_run_id}")
    base_filters = run.get("filters", {})
    notes = run.get("notes", "")

    if not base_filters:
        print(f"  ERROR: Run #{base_run_id} has no filters")
        sys.exit(1)

    new_filters = {**base_filters, **overrides}
    segment = "INFLUENCER_PLATFORMS"
    if "agencies" in notes.lower() or "IM_FIRST" in str(base_filters.get("icp_text", "")):
        segment = "IM_FIRST_AGENCIES"

    print(f"  Base: {notes}")
    print(f"  Overrides: {json.dumps(overrides, indent=2)}")
    return {"segment": segment, "filters": new_filters}


# ══════════════════════════════════════════════════════════════════════════════
# ТОЧКА ВХОДА
# Разбирает аргументы командной строки, загружает конфигурацию проекта
# из базы данных, определяет какие шаги выполнять и запускает pipeline.
# Можно запустить с любого шага: --from-step people (начать с импорта людей)
# ══════════════════════════════════════════════════════════════════════════════

STEPS = ["start", "blacklist", "prefilter", "scrape", "analyze", "verify",
         "export", "people", "findymail", "upload"]

def main():
    p = argparse.ArgumentParser(description="Universal Lead Generation Pipeline")
    p.add_argument("--project-id", type=int, required=True, help="Project ID from database")
    p.add_argument("--mode", choices=["natural", "structured", "lookalike", "expand"],
                   default="structured", help="Input mode for filter generation")
    p.add_argument("--segment", help="Segment slug (for structured mode)")
    p.add_argument("--input", dest="input_text", help="Mode 1: natural language description")
    p.add_argument("--filters", type=json.loads, help="Mode 1: JSON filters from Claude")
    p.add_argument("--examples", help="Mode 3: comma-separated example domains")
    p.add_argument("--base-run", type=int, help="Mode 4: run ID to clone")
    p.add_argument("--override", type=json.loads, default={}, help="Mode 4: JSON overrides")
    p.add_argument("--from-step", choices=STEPS, default="start")
    p.add_argument("--run-id", type=int, help="Resume existing run")
    p.add_argument("--apollo-csv", help="Apollo People CSV (platforms or single)")
    p.add_argument("--apollo-csv-agencies", help="Apollo People CSV for agencies segment")
    p.add_argument("--max-findymail", type=int, default=1500)
    p.add_argument("--prompt-file", help="Custom analysis prompt file")
    p.add_argument("--re-analyze", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    print(f"\n{'═'*60}")
    print(f"  Universal Pipeline — {ts()}")
    print(f"{'═'*60}")

    # Load project config from DB
    config = ProjectConfig(args.project_id)
    config.load()

    # Custom prompt override
    prompt_text = None
    if args.prompt_file:
        prompt_text = Path(args.prompt_file).read_text(encoding="utf-8")
        config.prompt_id = None
        print(f"  Custom prompt loaded: {args.prompt_file}")

    run_id = args.run_id or load_state(config.state_dir).get("run_id")

    # Re-analyze mode
    if args.re_analyze:
        if not run_id:
            print("ERROR: --run-id required for --re-analyze")
            sys.exit(1)
        params = {"model": "gpt-4o-mini"}
        if config.prompt_id:
            params["prompt_id"] = config.prompt_id
        elif prompt_text:
            params["prompt_text"] = prompt_text
        api("post", f"/pipeline/gathering/runs/{run_id}/re-analyze", params=params)
        return

    # ── Resolve filters (only for "start" step) ──
    steps = STEPS[STEPS.index(args.from_step):]
    mode_config = None
    needs_filters = "start" in steps

    if not needs_filters:
        pass
    elif args.mode == "natural":
        if not args.filters:
            print("ERROR: --filters JSON required for --mode natural")
            sys.exit(1)
        segment = "INFLUENCER_PLATFORMS"
        if any(kw in json.dumps(args.filters).lower() for kw in ["agency", "agencies", "im_first", "mcn"]):
            segment = "IM_FIRST_AGENCIES"
        mode_config = {"segment": segment, "filters": args.filters}
    elif args.mode == "structured":
        if not args.segment:
            print(f"ERROR: --segment required. Available: {', '.join(config.segments.keys())}")
            sys.exit(1)
        seg = config.get_segment(args.segment)
        # Build filters from segment data — or use provided ICP
        mode_config = {"segment": seg["name"], "filters": seg.get("default_filters", {})}
    elif args.mode == "lookalike":
        if not args.examples:
            print("ERROR: --examples required for --mode lookalike")
            sys.exit(1)
        examples = [d.strip() for d in args.examples.split(",") if d.strip()]
        mode_config = mode3_lookalike(config, examples)
    elif args.mode == "expand":
        if not args.base_run:
            print("ERROR: --base-run required for --mode expand")
            sys.exit(1)
        mode_config = mode4_expand(args.base_run, args.override)

    # Dry run
    if args.dry_run:
        filters = mode_config["filters"] if mode_config else {}
        print(f"\n  DRY RUN — no API calls")
        print(f"  Mode: {args.mode}")
        print(f"  Segment: {mode_config.get('segment', '?') if mode_config else '?'}")
        print(f"  Countries: {', '.join(filters.get('country_names', ['global']))}")
        print(f"  ICP: {filters.get('icp_text', '?')[:120]}...")
        print(f"  Steps: {' → '.join(steps)}")
        return

    # ── Steps 0-8: Backend gathering API ──
    if "start" in steps:
        if not mode_config:
            print("ERROR: no filters resolved")
            sys.exit(1)
        notes = f"{args.mode} — {args.input_text or args.segment or args.examples or f'expand#{args.base_run}'}"
        run_id = step0_start(config, mode_config["filters"], args.mode, args.input_text, notes)
        # Wait for Clay
        print("\n  Waiting for gathering to complete...")
        conn_errors = 0
        while True:
            time.sleep(15)
            try:
                r = httpx.get(f"{BACKEND_BASE}/api/pipeline/gathering/runs/{run_id}",
                              headers=BACKEND_HEADERS, timeout=30)
                phase = r.json().get("current_phase", "")
                if phase != "gather":
                    print(f"  Phase: {phase}")
                    break
                print("  ..gathering")
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException):
                conn_errors += 1
                if conn_errors >= 10:
                    print(f"  Too many errors. Resume: --from-step blacklist --run-id {run_id}")
                    sys.exit(1)
                time.sleep(15)

    if "blacklist" in steps and run_id:
        run_info = api("get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False)
        phase = run_info.get("current_phase", "")
        if phase == "awaiting_scope_ok":
            gates = api("get", f"/pipeline/gathering/approval-gates?project_id={args.project_id}",
                        raise_on_error=False)
            gate_list = gates if isinstance(gates, list) else gates.get("items", [])
            pending = [g for g in gate_list if g.get("gathering_run_id") == run_id and g.get("status") == "pending"]
            if pending:
                gate = pending[0]
                print(f"\n  ★ CP1 — gate #{gate['id']}, passed={gate.get('scope',{}).get('passed','?')}")
                print(f"  Pausing. Run with --from-step prefilter --run-id {run_id} after approval.")
                return
        elif phase in ("gathered", "gather"):
            cp1 = step2_blacklist(config, run_id)
            if cp1.get("gate_id"):
                print(f"  Pausing at CP1. Approve then: --from-step prefilter --run-id {run_id}")
                return

    if "prefilter" in steps and run_id:
        step3_prefilter(run_id)
    if "scrape" in steps and run_id:
        step4_scrape(run_id)
    if "analyze" in steps and run_id:
        cp2 = step5_analyze(config, run_id, prompt_text)
        if cp2.get("gate_id"):
            print(f"  Pausing at CP2. Approve then: --from-step verify --run-id {run_id}")
            return

    if "verify" in steps and run_id:
        cp3 = step6_prepare_verify(run_id)
        if cp3.get("gate_id"):
            print(f"  Pausing at CP3. Approve then: --from-step export --run-id {run_id}")
            return

    # ── Steps 9-12: Local execution ──
    if "export" in steps:
        targets = step9_export_targets(config, force=args.force)
    else:
        targets = load_json(config.state_dir / "targets.json") or []

    if "people" in steps:
        if args.apollo_csv:
            all_contacts = []
            seg_override = None
            if args.apollo_csv_agencies:
                # Two CSVs — platforms + agencies
                for slug, seg_data in config.segments.items():
                    if "platform" in slug.lower():
                        seg_override = seg_data["name"]
                        break
            c1 = step10_import_apollo_csv(config, args.apollo_csv, targets, force=args.force,
                                           segment_override=seg_override)
            all_contacts.extend(c1)
            if args.apollo_csv_agencies:
                agencies_name = None
                for slug, seg_data in config.segments.items():
                    if "agenc" in slug.lower():
                        agencies_name = seg_data["name"]
                        break
                c2 = step10_import_apollo_csv(config, args.apollo_csv_agencies, targets, force=True,
                                               segment_override=agencies_name)
                all_contacts.extend(c2)
                save_json(config.state_dir / "contacts.json", all_contacts)
                print(f"\n  Combined: {len(all_contacts)} contacts from both segments")
            contacts = all_contacts
        else:
            print("\n  ERROR: --apollo-csv required for people step")
            sys.exit(1)
    else:
        contacts = load_json(config.state_dir / "contacts.json") or \
                   load_json(config.state_dir / "enriched.json") or []

    if "findymail" in steps:
        contacts = asyncio.run(step11_findymail(config, contacts,
                                                 max_contacts=args.max_findymail, force=args.force))
    else:
        contacts = load_json(config.state_dir / "enriched.json") or contacts

    if "upload" in steps:
        step12_upload(config, contacts)


if __name__ == "__main__":
    main()
