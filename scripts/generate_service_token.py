"""Generate a service token for homeai-assis to call homeai-api.

Usage:
    python scripts/generate_service_token.py <JWT_SECRET_KEY> <TENANT_ID>

Example:
    python scripts/generate_service_token.py "my-secret-key" "00000000-0000-0000-0000-000000000001"

The generated token should be configured as BACKEND_API_KEY in homeai-assis.
"""

import sys
from datetime import datetime, timedelta

try:
    from jose import jwt
except ImportError:
    print("Error: python-jose not installed. Run: pip install python-jose[cryptography]")
    sys.exit(1)


def generate_service_token(jwt_secret: str, tenant_id: str, service_name: str = "homeai-assis") -> str:
    """Generate a long-lived JWT service token.
    
    Args:
        jwt_secret: The JWT secret key from homeai-api
        tenant_id: The tenant ID the service will access
        service_name: Name of the service (used as subject)
    
    Returns:
        JWT token string
    """
    # Token expires in 1 year (for service-to-service auth)
    expire = datetime.utcnow() + timedelta(days=365)
    
    payload = {
        "sub": f"service-{service_name}",
        "tenant_id": tenant_id,
        "role": "system",
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "service",
    }
    
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return token


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nError: Missing arguments")
        print("Usage: python scripts/generate_service_token.py <JWT_SECRET_KEY> <TENANT_ID>")
        sys.exit(1)
    
    jwt_secret = sys.argv[1]
    tenant_id = sys.argv[2]
    service_name = sys.argv[3] if len(sys.argv) > 3 else "homeai-assis"
    
    token = generate_service_token(jwt_secret, tenant_id, service_name)
    
    print("\n" + "=" * 60)
    print("SERVICE TOKEN GENERATED")
    print("=" * 60)
    print(f"\nService: {service_name}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Expires: 1 year from now")
    print("\nToken:")
    print("-" * 60)
    print(token)
    print("-" * 60)
    print("\nNext steps:")
    print("1. Go to Railway dashboard")
    print("2. Select homeai-assis service")
    print("3. Go to Variables")
    print("4. Set BACKEND_API_KEY = <token above>")
    print("5. Redeploy the service")
    print("=" * 60)


if __name__ == "__main__":
    main()
