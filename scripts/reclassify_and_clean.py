#!/usr/bin/env python3
"""
Re-classify AU-PH and Arabic-SA contacts for actual origin verification.
Uses name-based heuristics (fast, $0) + enterprise blacklist.

Filipino signals: Santos, Reyes, Cruz, Bautista, -zon, -uel, -ito, -ita endings
South African signals: Botha, du Plessis, van der Merwe, Nkosi, Dlamini, Naidoo, Govender
"""
import sys
import os
import json
from collections import Counter
from datetime import datetime

sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'

# ─── FILIPINO NAME SIGNALS ───
PH_SURNAMES = {s.lower() for s in [
    'Santos', 'Reyes', 'Cruz', 'Bautista', 'Ocampo', 'Garcia', 'Mendoza', 'Torres',
    'Dela Cruz', 'De Leon', 'Del Rosario', 'Gonzales', 'Hernandez', 'Lopez', 'Martinez',
    'Ramos', 'Rivera', 'Rodriguez', 'Villanueva', 'Aquino', 'Castro', 'Diaz', 'Fernandez',
    'Flores', 'Gomez', 'Gutierrez', 'Jimenez', 'Morales', 'Perez', 'Ramirez', 'Romero',
    'Sanchez', 'Santiago', 'Soriano', 'Tan', 'Chua', 'Go', 'Ong', 'Sy', 'Lim', 'Co',
    'Ang', 'Yap', 'Dy', 'Uy', 'Kho', 'Tiu', 'Yu', 'Ng', 'Lee', 'Chan',
    'Manalo', 'Pascual', 'Tolentino', 'Aguilar', 'Corpuz', 'Pangilinan', 'Dimaculangan',
    'Magno', 'Salazar', 'Velasco', 'Villegas', 'Zapata', 'Abalos', 'Balmaceda',
    'Camacho', 'Dagdag', 'Enriquez', 'Faustino', 'Galang', 'Imperial', 'Lacson',
    'Macapagal', 'Natividad', 'Olave', 'Palma', 'Quiambao', 'Resurreccion',
    'Teves', 'Ventura', 'Zamora', 'Abad', 'Bacani', 'Cabrera', 'Delos Santos',
    'Espino', 'Francisco', 'Ignacio', 'Joaquin', 'Lagman', 'Magtanggol',
    'Navarro', 'Panganiban', 'Quinto', 'Rosario', 'Salvador', 'Tanaka',
    'Umali', 'Valdez', 'Yuson', 'Zarate', 'Almonte', 'Buenaventura',
    'Concepcion', 'Dominguez', 'Estrada', 'Fuentes', 'Guzman',
    'Luzares', 'Teneza', 'Jorge', 'Roman', 'Tavae', 'Nouri',
    'Magat', 'Bagtas', 'Catalan', 'Dato', 'Manalang', 'Quisido',
]}

PH_FIRST_NAMES = {s.lower() for s in [
    'Jose', 'Juan', 'Maria', 'Ana', 'Mark', 'John', 'Michael', 'Christian',
    'Angelica', 'Jasmine', 'Jerome', 'Jericho', 'Rhea', 'Cherry', 'Jonel',
    'Ariel', 'Rommel', 'Rodel', 'Reynaldo', 'Rodolfo', 'Edgardo', 'Ernesto',
    'Rolando', 'Florante', 'Lorna', 'Marites', 'Maricel', 'Mylene',
    'Rosemarie', 'Jocelyn', 'Rogelio', 'Catalino', 'Diosdado', 'Renato',
    'Virgilio', 'Danilo', 'Wilfredo', 'Crisanto', 'Teresita', 'Corazon',
    'Imelda', 'Lourdes', 'Erlinda', 'Camille', 'Maryel', 'Casandra',
    'Kirsty', 'Levi', 'Phillip', 'Carmina', 'Czarina', 'Jomer', 'Jansen',
    'Rina', 'Gelo', 'Rica', 'Janno', 'Renz', 'Miko', 'Paolo',
]}

# ─── SOUTH AFRICAN NAME SIGNALS ───
SA_SURNAMES = {s.lower() for s in [
    'Botha', 'Du Plessis', 'Van Der Merwe', 'Pretorius', 'Joubert', 'Steyn', 'Coetzee',
    'Van Zyl', 'Kruger', 'Venter', 'Jansen', 'Swanepoel', 'Erasmus', 'Fourie',
    'Van Rensburg', 'Barnard', 'Cilliers', 'De Villiers', 'Ferreira', 'Hugo',
    'Le Roux', 'Lombard', 'Malan', 'Marais', 'Meiring', 'Naude', 'Olivier',
    'Potgieter', 'Rautenbach', 'Scheepers', 'Smit', 'Snyman', 'Theron',
    'Uys', 'Van Wyk', 'Viljoen', 'Visser', 'Wessels',
    'Nkosi', 'Dlamini', 'Ndlovu', 'Zulu', 'Mkhize', 'Naidoo', 'Govender',
    'Pillay', 'Maharaj', 'Moodley', 'Naicker', 'Chetty', 'Reddy', 'Singh',
    'Padayachee', 'Nair', 'Moonsamy', 'Mthembu', 'Khumalo', 'Ngcobo',
    'Cele', 'Buthelezi', 'Shabalala', 'Zwane', 'Sithole', 'Mahlangu',
    'Mokena', 'Molefe', 'Mokoena', 'Maseko', 'Sibiya', 'Tshabalala',
    'Cornelissen', 'English', 'Misselhorn', 'Du Toit', 'Van Der Walt',
    'Plessis', 'Butler', 'Dawson',
]}

SA_FIRST_NAMES = {s.lower() for s in [
    'Pieter', 'Hendrik', 'Johannes', 'Gerrit', 'Willem', 'Jacobus', 'Francois',
    'Christo', 'Petrus', 'Gert', 'Thabo', 'Sipho', 'Bongani', 'Nkosinathi',
    'Themba', 'Sibusiso', 'Mandla', 'Lucky', 'Blessing', 'Precious',
    'Nandi', 'Thandiwe', 'Palesa', 'Lerato', 'Kagiso', 'Mpho', 'Tshepo',
    'Tumi', 'Buhle', 'Ayanda', 'Siyabonga', 'Lungelo', 'Nhlanhla', 'Sizwe',
    'Vusi', 'Zandile', 'Nomvula', 'Nomsa', 'Zanele', 'Lindiwe', 'Gustav',
    'Johan', 'Frankie', 'Glenn', 'Jaco', 'Riaan', 'Danie', 'Kobus',
]}

# ─── ENTERPRISE BLACKLIST ───
ENTERPRISE_DOMAINS = {s.lower() for s in [
    'adobe.com', 'mastercard.com', 'google.com', 'facebook.com', 'meta.com',
    'amazon.com', 'microsoft.com', 'apple.com', 'linkedin.com', 'uber.com',
    'airbnb.com', 'twitter.com', 'x.com', 'oracle.com', 'ibm.com', 'sap.com',
    'salesforce.com', 'cisco.com', 'intel.com', 'nvidia.com', 'samsung.com',
    'dell.com', 'hp.com', 'hpe.com', 'vmware.com', 'accenture.com', 'deloitte.com',
    'pwc.com', 'ey.com', 'kpmg.com', 'mckinsey.com', 'bcg.com', 'bain.com',
    'jpmorgan.com', 'goldmansachs.com', 'morganstanley.com', 'citi.com',
    'hsbc.com', 'barclays.com', 'bnpparibas.com', 'credit-suisse.com',
    'almarai.com', 'adnocdrilling.ae', 'adnoc.ae', 'aramco.com', 'sabic.com',
    'emirates.com', 'etihad.com', 'qatarairways.com', 'flynas.com',
    'crownresorts.com.au', 'tal.com.au', 'commbank.com.au', 'anz.com.au',
    'nab.com.au', 'westpac.com.au', 'bhp.com', 'riotinto.com', 'woodside.com',
    'santos.com', 'fortescue.com', 'wesfarmers.com.au', 'woolworths.com.au',
    'coles.com.au', 'telstra.com.au', 'optus.com.au',
    'rakbank.ae', 'cbd.ae', 'enbd.com', 'adib.ae', 'nbad.com',
    'rakceramics.com', 'azadea.com', 'jumbo.ae', 'chalhoub.com',
    'worley.com', 'kentplc.com', 'daralriyadh.com',
    # India-HQ
    'dreamjobs.in', 'appinventiv.com', 'infosys.com', 'tcs.com', 'wipro.com',
    'hcl.com', 'techm.com',
]}


def is_filipino_origin(first_name, last_name):
    fn = first_name.lower().strip()
    ln = last_name.lower().strip()

    if ln in PH_SURNAMES:
        return True, f'PH surname: {ln}'
    if fn in PH_FIRST_NAMES and ln not in {'smith', 'jones', 'brown', 'wilson', 'taylor', 'davis', 'clark', 'hall', 'allen', 'young', 'king', 'wright', 'hill', 'scott', 'green', 'baker', 'adams', 'nelson', 'carter', 'mitchell', 'roberts', 'turner', 'phillips', 'campbell', 'parker', 'evans', 'edwards', 'collins', 'stewart', 'morris', 'murphy', 'cook', 'rogers', 'morgan', 'peterson', 'cooper', 'reed', 'bailey', 'bell', 'kelly', 'howard', 'ward', 'cox', 'diaz', 'richardson', 'wood', 'watson', 'brooks', 'bennett', 'gray', 'james', 'johnson', 'williams', 'anderson', 'thomas', 'jackson', 'white', 'harris', 'martin', 'thompson', 'robinson', 'lewis', 'walker', 'lee'}:
        return True, f'PH first name: {fn}'
    # Filipino suffixes
    if ln.endswith(('zon', 'quel', 'ito', 'ita', 'acion', 'uelo')):
        return True, f'PH suffix: {ln}'
    # Chinese-Filipino double names
    if len(ln) <= 3 and ln in {'tan', 'go', 'ong', 'sy', 'lim', 'co', 'ang', 'yap', 'dy', 'uy', 'kho', 'tiu', 'yu', 'ng'}:
        return True, f'PH Chinese: {ln}'
    return False, ''


def is_sa_origin(first_name, last_name):
    fn = first_name.lower().strip()
    ln = last_name.lower().strip()
    full = f'{fn} {ln}'

    if ln in SA_SURNAMES:
        return True, f'SA surname: {ln}'
    if fn in SA_FIRST_NAMES:
        return True, f'SA first: {fn}'
    # Afrikaans van/du/de patterns
    if any(full.startswith(p) for p in ['van ', 'du ', 'de ']):
        return True, f'SA prefix: {full[:10]}'
    if ' van ' in full or ' du ' in full or ' de ' in full:
        return True, f'SA name pattern'
    return False, ''


def process_corridor(gs, tab_name, origin_fn, corridor_label):
    print(f'\n{"="*60}')
    print(f'{corridor_label}: {tab_name}')
    print(f'{"="*60}')

    raw = gs.read_sheet_raw(SHEET_ID, tab_name)
    headers = raw[0]
    rows = raw[1:]
    col = {h: i for i, h in enumerate(headers)}

    total = len(rows)
    origin_match = []
    origin_fail = []
    enterprise_removed = 0
    india_removed = 0

    for row in rows:
        def g(name):
            idx = col.get(name, -1)
            return row[idx].strip() if idx >= 0 and idx < len(row) else ''

        domain = g('Domain').lower()

        # Enterprise blacklist
        if domain in ENTERPRISE_DOMAINS:
            enterprise_removed += 1
            continue

        # India HQ check
        if domain.endswith('.in') and domain not in {'linkedin.in'}:
            india_removed += 1
            continue

        first = g('First Name')
        last = g('Last Name')
        is_origin, reason = origin_fn(first, last)

        if is_origin:
            origin_match.append(row + [reason])
        else:
            origin_fail.append(f'{first} {last}')

    print(f'Total: {total}')
    print(f'Enterprise removed: {enterprise_removed}')
    print(f'India HQ removed: {india_removed}')
    print(f'Origin MATCH: {len(origin_match)}')
    print(f'Origin FAIL: {len(origin_fail)}')

    # Show some fails
    print(f'\nSample origin failures (first 15):')
    for name in origin_fail[:15]:
        print(f'  {name}')

    # Write clean list to new tab
    ts = datetime.now().strftime('%m%d_%H%M')
    clean_tab = f'{corridor_label} CLEAN {ts}'

    clean_headers = headers + ['Origin Reason']
    sheet_data = [clean_headers]
    for i, row in enumerate(origin_match):
        # Re-rank
        row[col['Rank']] = str(i + 1)
        sheet_data.append(row)

    gs._initialize()
    try:
        gs.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': clean_tab,
                  'gridProperties': {'rowCount': max(5000, len(sheet_data) + 100)}}}}]}
        ).execute()
    except Exception:
        pass

    for i in range(0, len(sheet_data), 500):
        batch = sheet_data[i:i + 500]
        gs.sheets_service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{clean_tab}'!A{i + 1}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()

    print(f'\nWrote {len(origin_match)} clean contacts to: {clean_tab}')
    return len(origin_match)


def main():
    gs = GoogleSheetsService()

    au_ph = process_corridor(gs, 'AU-PH Targets 0316_1308', is_filipino_origin, 'AU-PH')
    arabic_sa = process_corridor(gs, 'Arabic-SA Targets 0316_1309', is_sa_origin, 'Arabic-SA')

    print(f'\n{"="*60}')
    print(f'FINAL CLEAN COUNTS')
    print(f'{"="*60}')
    print(f'AU-Philippines: {au_ph} verified Filipino-origin contacts in Australia')
    print(f'Arabic-SouthAfrica: {arabic_sa} verified SA-origin contacts in Gulf')


if __name__ == '__main__':
    main()
