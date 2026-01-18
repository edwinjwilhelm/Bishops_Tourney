"""
Supabase Authentication Validator
Validates JWT tokens from Supabase for authenticated game connections
"""
import jwt
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from functools import lru_cache

# Supabase configuration
SUPABASE_URL = "https://wqceqyycatcjggmxunte.supabase.co"
SUPABASE_JWT_SECRET = None  # Will be fetched from Supabase

@lru_cache(maxsize=1)
def get_jwt_secret() -> str:
    """
    Fetch JWT secret from Supabase (cached)
    In production, this should be set as an environment variable
    """
    # For now, we'll need to get this from Supabase dashboard:
    # Project Settings -> API -> JWT Secret
    # You can also pass it as an environment variable
    import os
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise ValueError(
            "SUPABASE_JWT_SECRET not set. "
            "Get it from: https://supabase.com/dashboard/project/wqceqyycatcjggmxunte/settings/api"
        )
    return secret


def validate_supabase_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate a Supabase JWT token
    
    Args:
        token: JWT token from Supabase client
        
    Returns:
        User data dict if valid, None otherwise
        Contains: {
            'sub': 'user-uuid',
            'email': 'user@example.com',
            'role': 'authenticated',
            'exp': timestamp,
            ...
        }
    """
    if not token:
        return None
        
    try:
        secret = get_jwt_secret()
        
        # Decode and verify the JWT token
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True}
        )
        
        # Check if token is expired
        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            return None
            
        # Ensure this is an authenticated user
        if payload.get("role") != "authenticated":
            return None
            
        return payload
        
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


def get_user_email(token: str) -> Optional[str]:
    """
    Extract user email from Supabase token
    
    Args:
        token: JWT token from Supabase
        
    Returns:
        User's email address if valid, None otherwise
    """
    payload = validate_supabase_token(token)
    if payload:
        return payload.get("email")
    return None


def get_user_id(token: str) -> Optional[str]:
    """
    Extract user ID (UUID) from Supabase token
    
    Args:
        token: JWT token from Supabase
        
    Returns:
        User's UUID if valid, None otherwise
    """
    payload = validate_supabase_token(token)
    if payload:
        return payload.get("sub")
    return None
