"""The JSON:API resolver accepts only the approved provider and dataset."""
from copy import deepcopy
import pytest
from app import source


def catalogue():
    return {
        'data': {
            'type': 'datasets',
            'id': source.DATASET_ID,
            'relationships': {
                'wmsSource': {
                    'data': {'type': 'wmsSources', 'id': 'wms-1954'}
                }
            },
        },
        'included': [{
            'type': 'wmsSources',
            'id': 'wms-1954',
            'attributes': {
                'layer': source.LAYER,
                'version': '1.1.1',
                'format': 'image/jpeg',
                'url': 'https://services.hxgncontent.com/streaming/wms?access=SECRET',
            },
        }],
    }


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload


def test_resolve_from_official_jsonapi(monkeypatch):
    def get(url, **kwargs):
        assert url == source.METADATA
        assert kwargs['params'] == {'include': 'wmsSource'}
        assert kwargs['headers']['Accept'] == 'application/vnd.api+json'
        assert kwargs['allow_redirects'] is False
        return Response(catalogue())

    monkeypatch.setattr(source.requests, 'get', get)
    assert source.resolve() == 'https://services.hxgncontent.com/streaming/wms?access=SECRET'


@pytest.mark.parametrize('change', [
    ('data.id', 'another-dataset'),
    ('data.relationships.wmsSource.data.id', 'unrelated-source'),
    ('included.0.attributes.layer', 'unexpected-layer'),
    ('included.0.attributes.version', '1.3.0'),
    ('included.0.attributes.format', 'image/png'),
    ('included.0.attributes.url', 'https://evil.example/streaming/wms?access=SECRET'),
    ('included.0.attributes.url', 'http://services.hxgncontent.com/streaming/wms?access=SECRET'),
    ('included.0.attributes.url', 'https://services.hxgncontent.com/streaming/wms'),
    ('included.0.attributes.url', 'https://services.hxgncontent.com/streaming/wms?access=SECRET#fragment'),
    ('included.0.attributes.url', 'https://user:pass@services.hxgncontent.com/streaming/wms?access=SECRET'),
])
def test_reject_unapproved_metadata(monkeypatch, change):
    payload = deepcopy(catalogue())
    path, value = change
    obj = payload
    for key in path.split('.')[:-1]:
        obj = obj[int(key)] if key.isdecimal() else obj[key]
    obj[path.split('.')[-1]] = value
    monkeypatch.setattr(source.requests, 'get', lambda *a, **k: Response(payload))
    with pytest.raises(source.SourceError) as error:
        source.resolve()
    assert 'SECRET' not in str(error.value)


def test_reject_metadata_http_error(monkeypatch):
    monkeypatch.setattr(source.requests, 'get', lambda *a, **k: Response({}, 404))
    with pytest.raises(source.SourceError):
        source.resolve()


def test_reject_metadata_without_relation(monkeypatch):
    payload = catalogue()
    del payload['data']['relationships']
    monkeypatch.setattr(source.requests, 'get', lambda *a, **k: Response(payload))
    with pytest.raises(source.SourceError):
        source.resolve()
