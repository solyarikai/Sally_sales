#!/usr/bin/env python3.11
"""
Анализ A/B сиквенсов для IM-FIRST AGENCIES кампаний в SmartLead.
Собирает все варианты последовательностей, анализирует результаты.
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import os

# Пути к данным
SMARTLEAD_HUB = Path("/Users/sofia/Documents/GitHub/Sally_sales/sofia/projects/OnSocial/hub/smartlead_hub")
CAMPAIGNS_DIR = SMARTLEAD_HUB / "campaigns"
SEQUENCES_DOC = Path("/Users/sofia/Documents/GitHub/Sally_sales/sofia/projects/OnSocial/docs/smartlead_sequences_2026-03-26.md")

# IM-FIRST AGENCIES кампании
IM_AGENCIES_CAMPAIGNS = [
    "c-OnSocial_IM-FIRST AGENCIES #C",
    "c-OnSocial_IM-FIRST AGENCIES INDIA #C",
    "c-OnSocial_IM-FIRST AGENCIES EUROPE #C",
    "c-OnSocial_IM-FIRST AGENCIES US_CANADA_LATAM #C",
]

def load_campaign_data(campaign_name: str) -> List[Dict]:
    """Загружает данные кампании из CSV."""
    csv_file = CAMPAIGNS_DIR / f"{campaign_name}.csv"

    if not csv_file.exists():
        print(f"⚠️ Файл не найден: {csv_file}")
        return []

    data = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    return data

def extract_lead_status(campaign_data: List[Dict]) -> Dict[str, Dict]:
    """
    Извлекает статусы лидов.
    Возвращает {email: {status, first_name, last_name, company_name}}
    """
    leads = {}
    for row in campaign_data:
        email = row.get('email', '').strip()
        if email:
            leads[email] = {
                'status': row.get('lead_status', 'UNKNOWN'),
                'first_name': row.get('first_name', ''),
                'last_name': row.get('last_name', ''),
                'company_name': row.get('company_name', ''),
            }
    return leads

def extract_sequences_from_doc() -> Dict[str, List[Dict]]:
    """
    Парсит markdown документ и извлекает сиквенсы.
    Возвращает {campaign_name: [steps]}
    """
    if not SEQUENCES_DOC.exists():
        print(f"⚠️ Документ не найден: {SEQUENCES_DOC}")
        return {}

    content = SEQUENCES_DOC.read_text(encoding='utf-8')
    sequences = {}

    for campaign in IM_AGENCIES_CAMPAIGNS:
        # Ищем секцию кампании
        marker = f"### {campaign}"
        if marker not in content:
            print(f"⚠️ Кампания не найдена в документе: {campaign}")
            continue

        # Находим индекс начала кампании
        start_idx = content.find(marker)
        # Находим следующую кампанию (### ) или конец файла
        next_campaign_idx = content.find("\n### ", start_idx + 1)
        if next_campaign_idx == -1:
            campaign_content = content[start_idx:]
        else:
            campaign_content = content[start_idx:next_campaign_idx]

        # Извлекаем информацию о кампании (ID, статус, etc)
        lines = campaign_content.split('\n')
        campaign_info = lines[1] if len(lines) > 1 else ""

        sequences[campaign] = {
            'info': campaign_info,
            'content': campaign_content
        }

    return sequences

def analyze_responses() -> Dict[str, Dict]:
    """
    Анализирует все отклики по кампаниям.
    Возвращает статистику по положительным ответам.
    """
    results = {}

    for campaign in IM_AGENCIES_CAMPAIGNS:
        campaign_data = load_campaign_data(campaign)
        if not campaign_data:
            continue

        leads = extract_lead_status(campaign_data)

        # Подсчитываем статусы
        status_counts = defaultdict(int)
        for lead_info in leads.values():
            status_counts[lead_info['status']] += 1

        total = len(leads)
        positive_responses = status_counts.get('INTERESTED', 0) + status_counts.get('REPLIED', 0)

        results[campaign] = {
            'total_leads': total,
            'status_breakdown': dict(status_counts),
            'positive_responses': positive_responses,
            'response_rate': round((positive_responses / total * 100) if total > 0 else 0, 2),
            'leads': leads
        }

    return results

def print_analysis():
    """Выводит анализ A/B сиквенсов."""
    print("\n" + "="*80)
    print("🔬 АНАЛИЗ A/B СИКВЕНСОВ IM-FIRST AGENCIES")
    print("="*80)

    # Загружаем сиквенсы
    sequences = extract_sequences_from_doc()
    print(f"\n📋 Найдено кампаний: {len(sequences)}")

    for campaign, seq_data in sequences.items():
        print(f"\n{'─'*80}")
        print(f"📌 {campaign}")
        print(f"   {seq_data['info']}")

    # Анализируем результаты
    results = analyze_responses()
    print(f"\n{'='*80}")
    print("📊 РЕЗУЛЬТАТЫ ПО КАМПАНИЯМ")
    print("="*80)

    total_all = 0
    positive_all = 0

    for campaign in IM_AGENCIES_CAMPAIGNS:
        if campaign not in results:
            continue

        data = results[campaign]
        total = data['total_leads']
        positive = data['positive_responses']
        rate = data['response_rate']

        total_all += total
        positive_all += positive

        print(f"\n{campaign}")
        print(f"  Всего лидов: {total}")
        print(f"  Положительных ответов: {positive} ({rate}%)")
        print(f"  Статусы: {data['status_breakdown']}")

    print(f"\n{'='*80}")
    print(f"📈 ИТОГО:")
    print(f"  Всего лидов: {total_all}")
    print(f"  Всего положительных: {positive_all}")
    print(f"  Общий процент ответов: {round((positive_all / total_all * 100) if total_all > 0 else 0, 2)}%")
    print("="*80 + "\n")

def export_to_json(output_file: str = "im_agencies_ab_analysis.json"):
    """Экспортирует результаты в JSON."""
    sequences = extract_sequences_from_doc()
    results = analyze_responses()

    export_data = {
        'campaigns': {
            campaign: {
                'info': sequences.get(campaign, {}).get('info', ''),
                'stats': results.get(campaign, {})
            }
            for campaign in IM_AGENCIES_CAMPAIGNS
        },
        'summary': {
            'total_campaigns': len([c for c in IM_AGENCIES_CAMPAIGNS if c in results]),
            'total_leads': sum(r.get('total_leads', 0) for r in results.values()),
            'total_positive': sum(r.get('positive_responses', 0) for r in results.values()),
        }
    }

    # Убираем 'leads' из export для компактности
    for campaign_data in export_data['campaigns'].values():
        if 'leads' in campaign_data['stats']:
            del campaign_data['stats']['leads']

    output_path = Path(f"/Users/sofia/Documents/GitHub/Sally_sales/sofia/projects/OnSocial/hub/{output_file}")
    output_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False))
    print(f"✅ Результаты сохранены в: {output_path}")

if __name__ == "__main__":
    print("\n🚀 Запуск анализа IM-FIRST AGENCIES A/B сиквенсов...\n")

    print_analysis()
    export_to_json()
