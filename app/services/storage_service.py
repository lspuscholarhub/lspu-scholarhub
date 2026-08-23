"""
Cloud Storage Service — LSPU ScholarHub
Uses Cloudinary for permanent file storage that survives Railway redeploys.

Priority:
  1. Cloudinary — if CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET are set
  2. Local filesystem — fallback for development
"""

import os
import logging

logger = logging.getLogger(__name__)


def _cloudinary_configured():
    return all([
        os.environ.get('CLOUDINARY_CLOUD_NAME', '').strip(),
        os.environ.get('CLOUDINARY_API_KEY', '').strip(),
        os.environ.get('CLOUDINARY_API_SECRET', '').strip(),
    ])


def _init_cloudinary():
    """Configure Cloudinary from environment variables."""
    import cloudinary
    cloudinary.config(
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key    = os.environ.get('CLOUDINARY_API_KEY'),
        api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
        secure     = True,
    )


def upload_file(file_bytes: bytes, filename: str, folder: str,
                resource_type: str = 'auto') -> dict:
    """
    Upload file bytes to Cloudinary or local filesystem.

    Parameters
    ----------
    file_bytes    : raw file content
    filename      : original filename (used to determine extension)
    folder        : logical folder name e.g. 'registration', 'documents/47'
    resource_type : 'auto' lets Cloudinary detect PDF/image/etc.

    Returns
    -------
    dict with keys:
      success   : bool
      url       : public URL (Cloudinary) or local file path
      public_id : Cloudinary public_id (for deletion) or None
      provider  : 'cloudinary' | 'local'
      error     : error message if success=False
    """
    if _cloudinary_configured():
        return _upload_to_cloudinary(file_bytes, filename, folder, resource_type)
    return _upload_local(file_bytes, filename, folder)


def delete_file(public_id: str = None, file_path: str = None,
                resource_type: str = 'auto') -> dict:
    """
    Delete a file from Cloudinary or local filesystem.

    Pass public_id for Cloudinary files, file_path for local files.
    """
    if public_id and _cloudinary_configured():
        return _delete_from_cloudinary(public_id, resource_type)
    if file_path:
        return _delete_local(file_path)
    return {'success': False, 'error': 'No identifier provided'}


def get_file_bytes(public_id: str = None, file_path: str = None,
                   resource_type: str = 'auto') -> bytes | None:
    """
    Fetch raw bytes of a stored file.
    Used for OCR processing that needs the file content.
    """
    if public_id and _cloudinary_configured():
        return _fetch_from_cloudinary(public_id, resource_type)
    if file_path and os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            return f.read()
    return None


# ── Cloudinary implementation ─────────────────────────────────────────────────

def _upload_to_cloudinary(file_bytes, filename, folder, resource_type):
    try:
        import cloudinary.uploader
        _init_cloudinary()

        import io
        # Build a clean public_id (no extension — Cloudinary stores that separately)
        base = filename.rsplit('.', 1)[0] if '.' in filename else filename
        # Replace spaces and special chars
        import re
        base = re.sub(r'[^\w\-]', '_', base)
        public_id = f"scholarhub/{folder}/{base}"

        result = cloudinary.uploader.upload(
            io.BytesIO(file_bytes),
            public_id      = public_id,
            resource_type  = resource_type,
            overwrite       = True,
            use_filename    = False,
        )

        url = result.get('secure_url', '')
        pid = result.get('public_id', '')
        logger.info(f'Cloudinary upload OK: {pid} → {url}')
        return {
            'success':   True,
            'url':       url,
            'public_id': pid,
            'provider':  'cloudinary',
        }

    except Exception as e:
        logger.error(f'Cloudinary upload failed: {e}')
        return {'success': False, 'url': '', 'public_id': None,
                'provider': 'cloudinary', 'error': str(e)}


def _delete_from_cloudinary(public_id, resource_type):
    try:
        import cloudinary.uploader
        _init_cloudinary()
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        ok = result.get('result') == 'ok'
        return {'success': ok, 'error': None if ok else result.get('result')}
    except Exception as e:
        logger.error(f'Cloudinary delete failed: {e}')
        return {'success': False, 'error': str(e)}


def _fetch_from_cloudinary(public_id, resource_type):
    """Download file bytes from Cloudinary for OCR processing."""
    try:
        import cloudinary
        import urllib.request
        _init_cloudinary()

        # Build the URL for the resource
        import cloudinary.utils
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type = resource_type,
            secure        = True,
        )
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read()
    except Exception as e:
        logger.error(f'Cloudinary fetch failed: {e}')
        return None


# ── Local filesystem fallback ─────────────────────────────────────────────────

def _upload_local(file_bytes, filename, folder):
    try:
        from flask import current_app
        upload_root = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
        target_dir  = os.path.join(upload_root, folder)
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        logger.info(f'Local upload OK: {file_path}')
        return {
            'success':   True,
            'url':       file_path,   # local path used as "URL"
            'public_id': None,
            'provider':  'local',
        }
    except Exception as e:
        logger.error(f'Local upload failed: {e}')
        return {'success': False, 'url': '', 'public_id': None,
                'provider': 'local', 'error': str(e)}


def _delete_local(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}
