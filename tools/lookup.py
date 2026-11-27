"""Layer-d lookups by CAS for the SDS Section 10 checks.

Sources (as reachable from this session):
  ICSC (chemicalsafety.ilo.org)  - card text: chemical dangers, storage, fire fighting
  NIOSH Pocket Guide (cdc.gov)   - incompatibilities & reactivities
  CAMEO Chemicals (noaa.gov)     - reactivity profile, reactive groups, air & water reactions, incompatible absorbents
  GESTIS (dguv.de)               - search only (article text needs authorisation): returns the link for manual review
  PubChem                        - tried; reported as unavailable if the server refuses

Every result records the URL it came from and the retrieval date. Nothing is filled in when a source fails:
the entry carries status 'unreachable' or 'not found' instead.

Usage: python3 -I lookup.py OUT_DIR CAS [CAS ...]
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time

from bs4 import BeautifulSoup

TODAY = datetime.date.today().isoformat()
PAUSE = 1.0  # seconds between requests to the same site


def curl(url, out, data=None, cookie=None, referer=None):
    """Fetch with curl (uses the session proxy and CA bundle). Returns (http_code, text)."""
    cmd = ['curl', '-s', '-L', '--max-time', '60', '-o', out, '-w', '%{http_code}']
    if cookie:
        cmd += ['-c', cookie, '-b', cookie]
    if referer:
        cmd += ['-e', referer]
    for k, v in (data or {}).items():
        cmd += ['--data-urlencode', f'{k}={v}']
    cmd.append(url)
    code = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    text = open(out, encoding='utf-8', errors='ignore').read() if os.path.exists(out) else ''
    time.sleep(PAUSE)
    return code, text


def flat(html):
    return ' '.join(BeautifulSoup(html, 'html.parser').get_text(' ').split())


def between(text, start, ends, limit=1500):
    i = text.find(start)
    if i < 0:
        return None
    j = min([k for k in (text.find(e, i + len(start)) for e in ends) if k > 0] or [i + limit])
    return text[i + len(start):min(j, i + limit)].strip(' :')


def icsc(cas, work):
    url = f'https://chemicalsafety.ilo.org/dyn/icsc/showcard.listCards3?p_lang=en&p_cas_number={cas}'
    code, html = curl(url, os.path.join(work, f'icsc_list_{cas}.html'))
    if code != '200':
        return {'source': 'ICSC', 'status': 'unreachable', 'http': code, 'url': url}
    cards = sorted(set(re.findall(r'showcard\.display\?p_lang=en&(?:amp;)?p_card_id=(\d+)&(?:amp;)?p_version=(\d+)', html)))
    if not cards:
        return {'source': 'ICSC', 'status': 'not found', 'url': url}
    out = []
    for cid, ver in cards[:3]:
        curl_url = f'https://chemicalsafety.ilo.org/dyn/icsc/showcard.display?p_lang=en&p_card_id={cid}&p_version={ver}'
        code, card = curl(curl_url, os.path.join(work, f'icsc_{cid}.html'))
        t = flat(card)
        out.append({
            'card': cid, 'url': curl_url, 'http': code,
            'name': (re.search(r'ICSC:\s*\d+\s*(.*?)\s*(?:CAS|Date)', t) or [None, None])[1],
            'chemical_dangers': between(t, 'Chemical dangers', ['Formula:', 'Molecular mass', 'Occupational exposure']),
            'physical_dangers': between(t, 'Physical dangers', ['Chemical dangers']),
            'fire_and_explosion': between(t, 'FIRE & EXPLOSION', ['PREVENTION', 'Prevent build-up'], 600),
            'storage': between(t, 'STORAGE', ['PACKAGING', 'Prepared by']),
            'spillage': between(t, 'SPILLAGE DISPOSAL', ['CLASSIFICATION', 'STORAGE', 'PACKAGING']),
        })
    return {'source': 'ICSC', 'status': 'ok', 'cards': out, 'retrieved': TODAY}


_niosh_index = None


def niosh(cas, work):
    global _niosh_index
    if _niosh_index is None:
        code, html = curl('https://www.cdc.gov/niosh/npg/npgdcas.html', os.path.join(work, 'niosh_cas_index.html'))
        if code != '200':
            return {'source': 'NIOSH Pocket Guide', 'status': 'unreachable', 'http': code}
        soup = BeautifulSoup(html, 'html.parser')
        _niosh_index = {}
        for tr in soup.find_all('tr'):
            tds = [td.get_text(' ', strip=True) for td in tr.find_all('td')]
            links = [a.get('href') for a in tr.find_all('a') if a.get('href')]
            for c in tds:
                if re.fullmatch(r'\d{2,7}-\d{2}-\d', c) and links:
                    _niosh_index.setdefault(c, links[0])
    page = _niosh_index.get(cas)
    if not page:
        return {'source': 'NIOSH Pocket Guide', 'status': 'not found'}
    url = 'https://www.cdc.gov/niosh/npg/' + page.split('/')[-1]
    code, html = curl(url, os.path.join(work, f'niosh_{cas}.html'))
    t = flat(html)
    return {'source': 'NIOSH Pocket Guide', 'status': 'ok' if code == '200' else 'unreachable', 'http': code, 'url': url,
            'incompatibilities': between(t, 'Incompatibilities & Reactivities', ['Exposure Routes']),
            'retrieved': TODAY}


def cameo(cas, work):
    jar = os.path.join(work, 'cameo_cookies.txt')
    curl('https://cameochemicals.noaa.gov/search/simple', os.path.join(work, 'cameo_search.html'), cookie=jar)
    code, html = curl('https://cameochemicals.noaa.gov/search/simple/cas', os.path.join(work, f'cameo_res_{cas}.html'),
                      data={'cas': cas, 'submit': 'Search CAS Number'}, cookie=jar,
                      referer='https://cameochemicals.noaa.gov/search/simple')
    if code != '200':
        return {'source': 'CAMEO Chemicals', 'status': 'unreachable', 'http': code}
    ids = list(dict.fromkeys(re.findall(r'href="/chemical/(\d+)"', html)))
    if not ids:
        return {'source': 'CAMEO Chemicals', 'status': 'not found'}
    out = []
    for cid in ids[:2]:
        url = f'https://cameochemicals.noaa.gov/chemical/{cid}'
        code, sheet = curl(url, os.path.join(work, f'cameo_{cid}.html'), cookie=jar)
        t = flat(sheet)
        out.append({
            'id': cid, 'url': url, 'http': code,
            'name': (re.search(r'^(.*?)\s*\|\s*CAMEO', BeautifulSoup(sheet, 'html.parser').title.get_text() if BeautifulSoup(sheet, 'html.parser').title else '') or [None, None])[1],
            'air_water_reactions': between(t, 'Air & Water Reactions', ['Fire Hazard']),
            'reactivity_profile': between(t, 'Reactivity Profile', ['Belongs to the Following Reactive Group'], 2500),
            'reactive_groups': between(t, 'Belongs to the Following Reactive Group(s)', ['Potentially Incompatible Absorbents']),
            'incompatible_absorbents': between(t, 'Potentially Incompatible Absorbents', ['Response Recommendations']),
        })
    return {'source': 'CAMEO Chemicals', 'status': 'ok', 'datasheets': out, 'retrieved': TODAY}


def gestis(cas, work):
    url = f'https://gestis-api.dguv.de/api/search/en?stoffname=&nummern={cas}&summenformel=&volltextsuche=&anrecht=&exact=false'
    code, txt = curl(url, os.path.join(work, f'gestis_{cas}.json'))
    if code != '200':
        return {'source': 'GESTIS', 'status': 'unreachable', 'http': code}
    try:
        hits = [h for h in json.loads(txt) if h.get('cas_nr') == cas]
    except ValueError:
        hits = []
    if not hits:
        return {'source': 'GESTIS', 'status': 'not found'}
    return {'source': 'GESTIS', 'status': 'search only (article text needs authorisation; check manually)',
            'entries': [{'name': h.get('name'), 'zvg': h.get('zvg_nr'),
                         'url': f"https://gestis.dguv.de/data?name={h.get('zvg_nr')}&lang=en"} for h in hits[:3]]}


def pubchem(cas, work):
    url = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{cas}/property/MolecularFormula,IUPACName/JSON'
    code, txt = curl(url, os.path.join(work, f'pubchem_{cas}.json'))
    if code != '200':
        return {'source': 'PubChem', 'status': 'unreachable', 'http': code, 'note': txt[:160]}
    try:
        props = json.loads(txt)['PropertyTable']['Properties'][0]
    except (ValueError, KeyError, IndexError):
        return {'source': 'PubChem', 'status': 'not found'}
    return {'source': 'PubChem', 'status': 'ok', 'cid': props.get('CID'), 'formula': props.get('MolecularFormula'),
            'name': props.get('IUPACName'), 'url': f"https://pubchem.ncbi.nlm.nih.gov/compound/{props.get('CID')}",
            'retrieved': TODAY}


def lookup(cas, work):
    return {'cas': cas, 'results': [f(cas, work) for f in (icsc, niosh, cameo, gestis, pubchem)]}


if __name__ == '__main__':
    out_dir = sys.argv[1]
    work = os.path.join(out_dir, 'raw')
    os.makedirs(work, exist_ok=True)
    for cas in sys.argv[2:]:
        res = lookup(cas, work)
        json.dump(res, open(os.path.join(out_dir, f'lookup_{cas}.json'), 'w'), indent=1, ensure_ascii=False)
        print(cas, [(r['source'], r['status']) for r in res['results']])
