"""Allowlisted historical raster sources. Never accept provider URLs from clients.

Optional providers are activated only after server-side credentials are installed.
The map-sheet service covers 1901–1971: it is NOT guaranteed to show 1940.
"""
import os
import hashlib

_verified_key = None


def datafordeler_key():
    key = os.getenv('PLOTTER_DATAFORDELER_APIKEY', '')
    return key if 8 <= len(key) <= 4096 and not any(c.isspace() for c in key) else ''


def mark_verified(key):
    global _verified_key
    _verified_key = hashlib.sha256(key.encode()).digest() if key else None

SOURCES = {
    'dmp_1954': {
        'label': 'DDO 1954 · luftfoto',
        'period': '1954',
        'provider': 'Danmarks Miljøportal / Hexagon',
        'attribution': 'DDO 1954 © Hexagon · Efterkrigsmateriale · Print i faktisk størrelse / 100 %',
        'year': '1954',
        'default_mpp': 0.25,
        'mpp': (0.25, 0.5, 1),
        'kind': 'dmp',
    },
    'lave_maalebordsblade': {
        'label': 'Lave målebordsblade · topografisk kort',
        'period': '1901–1971 · årstal varierer pr. kortblad',
        'provider': 'Datafordeleren / Klimadatastyrelsen',
        'attribution': 'Klimadatastyrelsen · Lave målebordsblade · CC BY 4.0 · Udsnit/resampling · udgaveår varierer',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'year': None,
        'default_mpp': 1,
        'mpp': (0.5, 1, 2, 4),
        'kind': 'datafordeler',
        'credential_env': 'PLOTTER_DATAFORDELER_APIKEY',
    },
    'lw_1944': {
        'label': 'Luftwaffe 1944 · fotokort',
        'period': '1944',
        'provider': 'FlyFotos.dk',
        'attribution': 'LW1944 · kræver dokumenteret brugsret',
        'year': '1944',
        'default_mpp': 1,
        'mpp': (0.5, 1, 2, 4),
        'kind': 'pending',
        'reason': 'Kræver verificeret WMS-adgang og tilladelse til eksport fra FlyFotos.dk.',
    },
    'ia_1945': {
        'label': 'Allierede 1945 · luftfoto',
        'period': '1945',
        'provider': 'FlyFotos.dk',
        'attribution': 'IA_1945 · kræver dokumenteret brugsret',
        'year': '1945',
        'default_mpp': 1,
        'mpp': (0.5, 1, 2, 4),
        'kind': 'pending',
        'reason': 'Kræver verificeret WMS-adgang og tilladelse til eksport fra FlyFotos.dk.',
    },
}


def get(profile='dmp_1954'):
    if profile not in SOURCES:
        raise ValueError('Ukendt kortkilde.')
    return SOURCES[profile]


def available(profile='dmp_1954'):
    spec = get(profile)
    if spec['kind'] == 'dmp':
        return True
    if spec['kind'] == 'datafordeler':
        key = datafordeler_key()
        # Never expose the key to the UI, logging or persisted jobs.
        return bool(key) and _verified_key == hashlib.sha256(key.encode()).digest()
    return False


def require_available(profile='dmp_1954'):
    spec = get(profile)
    if not available(profile):
        if spec['kind'] == 'datafordeler':
            raise ValueError(datafordeler_reason())
        raise ValueError(spec['reason'])
    return spec


def datafordeler_reason():
    return ('Datafordeler-adgangen har ikke bestået billedtesten. Kontrollér servernøglen og genstart appen.'
            if datafordeler_key() else 'Kræver Datafordeler-API-nøgle på serveren.')


def catalogue():
    entries = []
    for profile, spec in SOURCES.items():
        is_ready = available(profile)
        entries.append({
            'id': profile,
            'label': spec['label'],
            'period': spec['period'],
            'provider': spec['provider'],
            'attribution': spec['attribution'],
            'license_url': spec.get('license_url'),
            'available': is_ready,
            'reason': '' if is_ready else (
                datafordeler_reason()
                if spec['kind'] == 'datafordeler' else spec['reason']),
            'default_mpp': spec['default_mpp'],
            'meters_per_pixel': list(spec['mpp']),
        })
    return entries
