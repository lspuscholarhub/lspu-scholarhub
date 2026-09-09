"""
Password validation service — enforces complexity requirements.

Requirements:
  - Minimum 8 characters
  - At least one uppercase letter
  - At least one lowercase letter
  - At least one number
"""
import re


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password complexity.
    
    Returns:
        (is_valid, error_message)
        error_message is empty string if valid.
    """
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long.'
    
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one number.'
    
    return True, ''


def get_password_requirements_html() -> str:
    """Return HTML listing password requirements (for templates)."""
    return '''
    <div class="form-text">
        <small class="text-muted">
            Password must be at least 8 characters with:
            <ul class="mb-0 mt-1" style="list-style:none;padding-left:0;">
                <li>✓ At least one uppercase letter</li>
                <li>✓ At least one lowercase letter</li>
                <li>✓ At least one number</li>
            </ul>
        </small>
    </div>
    '''
