#!/usr/bin/env python3
"""
SmartLead A/B Test Analysis — IM-FIRST AGENCIES
================================================

Анализирует A/B варианты сиквенсов для кампаний IM-FIRST AGENCIES.
Собирает данные о положительных ответах (REPLIED статус) по каждой кампании.

✅ Запускать НА HETZNER: ssh hetzner "python3 sofia/scripts/smartlead_im_agencies_ab_analysis.py"

Требует:
- SMARTLEAD_API_KEY в .env
- Интернет-доступ к SmartLead API
"""

import os
import httpx
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# SmartLead API конфиг
BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

# Кампании для анализа
CAMPAIGNS = {
    "c-OnSocial_IM-FIRST AGENCIES #C": 3050462,
    "c-OnSocial_IM-FIRST AGENCIES INDIA #C": 3063527,
    "c-OnSocial_IM-FIRST AGENCIES EUROPE #C": 3064335,
    "c-OnSocial_IM-FIRST AGENCIES US_CANADA_LATAM #C": 3071851,
}

# A/B вариантов по кампаниям (из документации)
AB_VARIANTS = {
    3050462: {  # IM-FIRST AGENCIES #C
        "name": "Main Global Campaign",
        "variants": [
            {
                "step": 1,
                "subject": "{{first_name}}, 450M influencer profiles ready for your API",
                "variant": "V1_Intro_450M",
                "type": "A",
                "days": 0
            },
            {
                "step": 2,
                "subject": "(thread)",
                "variant": "V1_HypeAuditor_Comparison",
                "type": "B",
                "days": 1
            },
        ]
    },
    3063527: {  # IM-FIRST AGENCIES INDIA #C
        "name": "India Campaign",
        "variants": [
            {
                "step": 1,
                "subject": "(thread)",
                "variant": "Empty_Step1",
                "type": "A",
                "days": 0
            },
            # Need to fetch from API for complete info
        ]
    },
    3064335: {  # IM-FIRST AGENCIES EUROPE #C
        "name": "Europe Campaign",
        "variants": [
            {
                "step": 1,
                "subject": "{{first_name}}, 450M influencer profiles are ready for your API",
                "variant": "V2_Intro_Profiles_Ready",
                "type": "A",
                "days": 0
            },
        ]
    },
    3071851: {  # IM-FIRST AGENCIES US_CANADA_LATAM #C
        "name": "Americas Campaign",
        "variants": [
            {
                "step": 1,
                "subject": "{{first_name}}, 450M influencer profiles ready for your API",
                "variant": "V1_Intro_450M",
                "type": "A",
                "days": 0
            },
        ]
    },
}


def api_get(path: str, params: Dict = None) -> Dict:
    """Запрос к SmartLead API с аутентификацией."""
    if not API_KEY:
        raise ValueError("❌ SMARTLEAD_API_KEY не установлен в .env")

    query = params or {}
    query["api_key"] = API_KEY

    try:
        resp = httpx.get(f"{BASE_URL}{path}", params=query, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        print(f"❌ API ошибка: {e}")
        return {}


def get_campaign_statistics(campaign_id: int) -> Dict:
    """Получить статистику кампании."""
    print(f"  📊 Загружаем статистику кампании {campaign_id}...")
    return api_get(f"/campaigns/{campaign_id}/statistics")


def get_campaign_leads_by_status(campaign_id: int, status: str = "REPLIED", limit: int = 100) -> List[Dict]:
    """Получить лидов по статусу (например, те кто ответил)."""
    leads = []
    offset = 0

    while True:
        print(f"  👥 Загружаем лидов со статусом '{status}' (offset={offset})...")
        data = api_get(
            f"/campaigns/{campaign_id}/leads",
            {"status": status, "offset": offset, "limit": limit}
        )

        if not data:
            break

        campaign_leads = data.get("data", [])
        if not campaign_leads:
            break

        leads.extend(campaign_leads)
        total = data.get("total_leads", 0)
        print(f"    ✓ Получено {len(leads)} из {total}")

        if len(leads) >= total:
            break

        offset += limit

    return leads


def get_lead_details(lead_id: int) -> Optional[Dict]:
    """Получить детали конкретного лида."""
    return api_get(f"/leads/{lead_id}")


def get_lead_message_history(lead_id: int) -> Dict:
    """Получить историю сообщений с лидом."""
    return api_get(f"/leads/{lead_id}/messages")


def analyze_campaign(campaign_id: int, campaign_name: str) -> Dict:
    """Анализ одной кампании."""
    print(f"\n{'='*80}")
    print(f"🔬 Анализ: {campaign_name}")
    print(f"   Campaign ID: {campaign_id}")
    print(f"{'='*80}")

    # Получить статистику
    stats = get_campaign_statistics(campaign_id)
    print(f"\n📈 Статистика:")
    print(f"  Отправлено: {stats.get('total_sent', 0)}")
    print(f"  Открыто: {stats.get('total_opened', 0)}")
    print(f"  Кликнуто: {stats.get('total_clicked', 0)}")
    print(f"  Ответов: {stats.get('total_replied', 0)}")
    print(f"  Отказано: {stats.get('total_bounced', 0)}")

    # Получить лидов с положительными ответами
    replied_leads = get_campaign_leads_by_status(campaign_id, "REPLIED")
    print(f"\n💬 Положительные ответы: {len(replied_leads)}")

    # Получить детали каждого ответившего лида
    replied_details = []
    for lead in replied_leads[:5]:  # Ограничиваем для примера
        lead_data = lead.get("lead", lead)
        print(f"\n  📧 {lead_data.get('email')} ({lead_data.get('first_name')} {lead_data.get('last_name')})")
        print(f"      Компания: {lead_data.get('company_name')}")

        # Получить историю сообщений
        messages = get_lead_message_history(lead_data.get('id'))
        if messages:
            print(f"      История: {json.dumps(messages, indent=8, ensure_ascii=False)[:200]}...")

        replied_details.append({
            "email": lead_data.get('email'),
            "name": f"{lead_data.get('first_name')} {lead_data.get('last_name')}",
            "company": lead_data.get('company_name'),
            "status": lead.get('status'),
        })

    # A/B информация
    variants = AB_VARIANTS.get(campaign_id, {}).get("variants", [])
    print(f"\n🎯 A/B варианты ({len(variants)}):")
    for v in variants:
        print(f"  Step {v.get('step')}: {v.get('variant')} ({v.get('type')})")
        print(f"    Subject: {v.get('subject')}")

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "statistics": stats,
        "total_replied": len(replied_leads),
        "replied_leads": replied_details,
        "variants": variants,
        "response_rate": round(
            (len(replied_leads) / stats.get('total_sent', 1) * 100) if stats.get('total_sent') else 0,
            2
        ),
    }


def compare_campaigns(results: List[Dict]) -> None:
    """Сравнить результаты между кампаниями."""
    print(f"\n{'='*80}")
    print(f"📊 СРАВНЕНИЕ A/B РЕЗУЛЬТАТОВ")
    print(f"{'='*80}")

    print("\n| Кампания | Отправлено | Ответов | % Ответов |")
    print("|----------|-----------|---------|-----------|")

    for r in results:
        sent = r.get('statistics', {}).get('total_sent', 0)
        replies = r.get('total_replied', 0)
        rate = r.get('response_rate', 0)
        name = r.get('campaign_name', 'Unknown')[:30]
        print(f"| {name:30} | {sent:9} | {replies:7} | {rate:7.2f}% |")

    # Найти лучший вариант
    best = max(results, key=lambda x: x.get('response_rate', 0))
    print(f"\n🏆 ЛУЧШИЙ РЕЗУЛЬТАТ:")
    print(f"   {best.get('campaign_name')}")
    print(f"   Response Rate: {best.get('response_rate')}%")
    print(f"   Положительных ответов: {best.get('total_replied')}")


def export_results(results: List[Dict], output_dir: str = None) -> None:
    """Экспортировать результаты в JSON."""
    if output_dir is None:
        output_dir = "/Users/sofia/Documents/GitHub/Sally_sales/sofia/projects/OnSocial/hub"

    output_path = Path(output_dir) / f"im_agencies_ab_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export_data = {
        "analysis_date": datetime.now().isoformat(),
        "campaigns": results,
        "summary": {
            "total_campaigns": len(results),
            "total_sent": sum(r.get('statistics', {}).get('total_sent', 0) for r in results),
            "total_replied": sum(r.get('total_replied', 0) for r in results),
            "avg_response_rate": round(
                sum(r.get('response_rate', 0) for r in results) / len(results) if results else 0,
                2
            ),
        }
    }

    output_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False))
    print(f"\n✅ Результаты сохранены: {output_path}")


def main():
    print(f"\n🚀 SmartLead A/B Test Analysis — IM-FIRST AGENCIES")
    print(f"   Дата: {datetime.now().isoformat()}")

    if not API_KEY:
        print(f"❌ ОШИБКА: SMARTLEAD_API_KEY не установлен!")
        print(f"   Убедитесь, что .env файл содержит SMARTLEAD_API_KEY=your_key")
        return

    results = []

    # Анализ каждой кампании
    for campaign_name, campaign_id in CAMPAIGNS.items():
        try:
            result = analyze_campaign(campaign_id, campaign_name)
            results.append(result)
        except Exception as e:
            print(f"❌ Ошибка при анализе {campaign_name}: {e}")

    # Сравнение результатов
    if results:
        compare_campaigns(results)
        export_results(results)
    else:
        print("❌ Нет результатов для анализа")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
