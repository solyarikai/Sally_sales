#!/usr/bin/env python3
import asyncio, sys, os
sys.path.insert(0, '/app')
from app.services.smartlead_service import SmartleadService

async def main():
    sl = SmartleadService()
    steps = await sl.get_campaign_sequences('3042239')
    sequences = []
    for s in steps:
        subj = s.get('subject', '')
        if subj:
            subj = subj.replace('{{company_name}}', '{{first_name}}')
        sequences.append({
            'seq_number': s['seq_number'],
            'seq_delay_details': s.get('seq_delay_details', {}),
            'subject': subj,
            'email_body': s['email_body'],
        })
    result = await sl.set_campaign_sequences('3042239', sequences)
    print(f'Updated: {result}')
    new = await sl.get_campaign_sequences('3042239')
    subj = new[0].get('subject', '')
    print(f'New subject: {subj}')

if __name__ == '__main__':
    asyncio.run(main())
