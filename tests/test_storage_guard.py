"""Uploads must never be written somewhere they will be lost.

A deployed container replaces its disk on the next deploy, so the local fallback
is only valid on a developer's machine. When there is no durable place to put a
file, the upload has to fail loudly instead of handing back a path that will
stop existing.
"""
import os

import pytest

from app.services import storage_service


@pytest.fixture()
def no_cloudinary(app, tmp_path, monkeypatch):
    for name in ('CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY',
                 'CLOUDINARY_API_SECRET', 'ALLOW_LOCAL_UPLOADS',
                 'RAILWAY_ENVIRONMENT', 'RAILWAY_PROJECT_ID'):
        monkeypatch.delenv(name, raising=False)
    uploads = tmp_path / 'uploads'
    app.config['UPLOAD_FOLDER'] = str(uploads)
    return uploads


def test_deployed_host_refuses_instead_of_losing_the_file(no_cloudinary, monkeypatch):
    monkeypatch.setenv('RAILWAY_ENVIRONMENT', 'production')

    result = storage_service.upload_file(b'%PDF-1.4', 'cor.pdf', 'registration/1')

    assert result['success'] is False
    assert result['provider'] == 'none'
    assert result['url'] == ''
    assert 'not available right now' in result['error']
    assert storage_service.storage_ready() is False
    assert not no_cloudinary.exists()   # nothing was written anywhere


def test_development_still_uses_the_local_disk(no_cloudinary, monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'development')

    result = storage_service.upload_file(b'%PDF-1.4', 'cor.pdf', 'registration/1')

    assert result['success'] is True
    assert result['provider'] == 'local'
    assert os.path.exists(result['url'])


def test_explicit_opt_in_allows_a_durable_local_volume(no_cloudinary, monkeypatch):
    monkeypatch.setenv('RAILWAY_ENVIRONMENT', 'production')
    monkeypatch.setenv('ALLOW_LOCAL_UPLOADS', 'true')

    result = storage_service.upload_file(b'%PDF-1.4', 'cor.pdf', 'registration/1')

    assert result['success'] is True
    assert result['provider'] == 'local'
