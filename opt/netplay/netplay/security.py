"""
Security Module for Bishops Game Server
Provides authentication, rate limiting, input sanitization, and CSRF protection
"""
import hashlib
import hmac
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from functools import wraps

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


# =============================================================================
# AUTHENTICATION
# =============================================================================

class AuthManager:
    """Manages admin authentication with session tokens"""
    
    def __init__(self, admin_password: str):
        """
        Args:
            admin_password: Plain text password (will be hashed)
        """
        # Hash the admin password with salt
        self.salt = secrets.token_hex(16)
        self.admin_password_hash = self._hash_password(admin_password, self.salt)
        
        # Store active sessions: {token: expiry_time}
        self.sessions: Dict[str, datetime] = {}
        
        # Session timeout (24 hours)
        self.session_duration = timedelta(hours=24)
    
    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password with salt using SHA-256"""
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        """Verify if provided password matches admin password"""
        return hmac.compare_digest(
            self._hash_password(password, self.salt),
            self.admin_password_hash
        )
    
    def create_session(self, password: str) -> Optional[str]:
        """
        Create new session token if password is correct
        
        Returns:
            Session token string, or None if password incorrect
        """
        if not self.verify_password(password):
            return None
        
        # Generate secure random token
        token = secrets.token_urlsafe(32)
        
        # Set expiry time
        self.sessions[token] = datetime.now() + self.session_duration
        
        return token
    
    def verify_session(self, token: str) -> bool:
        """Verify if session token is valid and not expired"""
        if token not in self.sessions:
            return False
        
        # Check if expired
        if datetime.now() > self.sessions[token]:
            del self.sessions[token]
            return False
        
        return True
    
    def revoke_session(self, token: str):
        """Revoke (logout) a session token"""
        if token in self.sessions:
            del self.sessions[token]
    
    def cleanup_expired_sessions(self):
        """Remove all expired sessions"""
        now = datetime.now()
        expired = [token for token, expiry in self.sessions.items() if now > expiry]
        for token in expired:
            del self.sessions[token]


# =============================================================================
# RATE LIMITING
# =============================================================================

class RateLimiter:
    """IP-based rate limiting to prevent abuse"""
    
    def __init__(self):
        # Track requests per IP: {ip: [timestamp, timestamp, ...]}
        self.requests: Dict[str, list] = defaultdict(list)
        
        # Rate limits (requests per time window)
        self.limits = {
            'ai_action': (5, 3600),      # 5 AI actions per hour
            'create_room': (10, 3600),    # 10 rooms per hour
            'general': (100, 60),         # 100 requests per minute
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for X-Forwarded-For header (if behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host
    
    def _cleanup_old_requests(self, ip: str, window: int):
        """Remove requests older than the time window"""
        cutoff = time.time() - window
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > cutoff]
    
    def check_limit(self, request: Request, limit_type: str = 'general') -> bool:
        """
        Check if request should be allowed
        
        Args:
            request: FastAPI request object
            limit_type: Type of limit to check ('ai_action', 'create_room', 'general')
        
        Returns:
            True if allowed, False if rate limit exceeded
        """
        ip = self._get_client_ip(request)
        max_requests, window = self.limits.get(limit_type, (100, 60))
        
        # Clean up old requests
        self._cleanup_old_requests(ip, window)
        
        # Check if limit exceeded
        if len(self.requests[ip]) >= max_requests:
            return False
        
        # Add current request
        self.requests[ip].append(time.time())
        return True
    
    def get_remaining(self, request: Request, limit_type: str = 'general') -> int:
        """Get remaining requests for this IP"""
        ip = self._get_client_ip(request)
        max_requests, window = self.limits.get(limit_type, (100, 60))
        self._cleanup_old_requests(ip, window)
        return max(0, max_requests - len(self.requests[ip]))


# =============================================================================
# INPUT SANITIZATION
# =============================================================================

class InputSanitizer:
    """Sanitize user inputs to prevent XSS and injection attacks"""
    
    # Characters to strip/escape
    DANGEROUS_CHARS = ['<', '>', '"', "'", '&', '`', '\x00']
    
    # Patterns that suggest attack attempts
    SUSPICIOUS_PATTERNS = [
        r'<script',
        r'javascript:',
        r'onerror=',
        r'onload=',
        r'onclick=',
        r'<iframe',
        r'eval\(',
        r'expression\(',
    ]
    
    @staticmethod
    def sanitize_string(text: str, max_length: int = 200) -> str:
        """
        Sanitize string input
        
        Args:
            text: Input string
            max_length: Maximum allowed length
        
        Returns:
            Sanitized string
        """
        if not isinstance(text, str):
            return ""
        
        # Normalize unicode (prevent overlong UTF-8 attacks)
        text = text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
        
        # Limit length
        text = text[:max_length]
        
        # Strip null bytes
        text = text.replace('\x00', '')
        
        # Escape HTML special characters
        replacements = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '&': '&amp;',
            '`': '&#x60;',
        }
        for char, escape in replacements.items():
            text = text.replace(char, escape)
        
        return text.strip()
    
    @staticmethod
    def sanitize_room_name(name: str) -> str:
        """Sanitize room name (alphanumeric + spaces/dashes only)"""
        # Allow only safe characters
        import re
        name = re.sub(r'[^a-zA-Z0-9\s\-_]', '', name)
        return InputSanitizer.sanitize_string(name, max_length=50)
    
    @staticmethod
    def sanitize_username(username: str) -> str:
        """Sanitize username"""
        import re
        username = re.sub(r'[^a-zA-Z0-9_\-]', '', username)
        return InputSanitizer.sanitize_string(username, max_length=30)
    
    @staticmethod
    def is_suspicious(text: str) -> bool:
        """Check if text contains suspicious patterns"""
        import re
        text_lower = text.lower()
        for pattern in InputSanitizer.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False


# =============================================================================
# CSRF PROTECTION
# =============================================================================

class CSRFProtection:
    """Cross-Site Request Forgery protection"""
    
    def __init__(self):
        # Store valid tokens: {token: creation_time}
        self.tokens: Dict[str, datetime] = {}
        self.token_lifetime = timedelta(hours=1)
    
    def generate_token(self) -> str:
        """Generate new CSRF token"""
        token = secrets.token_urlsafe(32)
        self.tokens[token] = datetime.now()
        return token
    
    def verify_token(self, token: str) -> bool:
        """Verify CSRF token is valid and not expired"""
        if token not in self.tokens:
            return False
        
        # Check expiry
        if datetime.now() > self.tokens[token] + self.token_lifetime:
            del self.tokens[token]
            return False
        
        # Valid - remove to prevent reuse
        del self.tokens[token]
        return True
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens"""
        now = datetime.now()
        expired = [
            token for token, created in self.tokens.items()
            if now > created + self.token_lifetime
        ]
        for token in expired:
            del self.tokens[token]


# =============================================================================
# MIDDLEWARE & DECORATORS
# =============================================================================

def require_auth(auth_manager: AuthManager):
    """Decorator to require authentication for route"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find Request object in args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found"
                )
            
            # Check for session token in cookie or header
            token = request.cookies.get("session_token")
            if not token:
                token = request.headers.get("Authorization", "").replace("Bearer ", "")
            
            if not token or not auth_manager.verify_session(token):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_rate_limit(rate_limiter: RateLimiter, limit_type: str = 'general'):
    """Decorator to enforce rate limiting"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find Request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found"
                )
            
            # Check rate limit
            if not rate_limiter.check_limit(request, limit_type):
                remaining = rate_limiter.get_remaining(request, limit_type)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again later.",
                    headers={"Retry-After": "3600"}
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# INITIALIZATION
# =============================================================================

def create_security_components(admin_password: str):
    """
    Create all security components
    
    Args:
        admin_password: Admin password (from environment variable)
    
    Returns:
        Tuple of (auth_manager, rate_limiter, csrf_protection, sanitizer)
    """
    auth_manager = AuthManager(admin_password)
    rate_limiter = RateLimiter()
    csrf_protection = CSRFProtection()
    sanitizer = InputSanitizer()
    
    return auth_manager, rate_limiter, csrf_protection, sanitizer
