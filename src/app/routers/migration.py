"""Temporary migration endpoint - DELETE AFTER USE."""

from fastapi import APIRouter, HTTPException, Query

from ..config.database import get_pool

router = APIRouter(tags=["Migration"])

# Secret key to prevent unauthorized access
MIGRATION_SECRET = "migrate-multitenancy-2026"


@router.post("/migrate/multitenancy")
async def run_multitenancy_migration(
    secret: str = Query(..., description="Migration secret key"),
    phone: str = Query(..., description="Your WhatsApp phone in E.164 format"),
    name: str = Query(default="Pablo", description="Your display name"),
):
    """
    Run multitenancy migration.
    
    THIS ENDPOINT IS TEMPORARY - DELETE AFTER MIGRATION.
    """
    if secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    pool = await get_pool()
    
    results = []
    
    try:
        async with pool.acquire() as conn:
            # 1. Create phone_tenant_mapping table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS phone_tenant_mapping (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    phone VARCHAR(20) NOT NULL,
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    is_primary BOOLEAN DEFAULT false,
                    display_name VARCHAR(100),
                    verified_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    CONSTRAINT unique_phone UNIQUE (phone)
                )
            """)
            results.append("Created phone_tenant_mapping table")
            
            # 2. Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_phone_tenant_phone ON phone_tenant_mapping(phone)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_phone_tenant_tenant ON phone_tenant_mapping(tenant_id)
            """)
            results.append("Created indexes")
            
            # 3. Extend tenants table
            await conn.execute("""
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS home_name VARCHAR(100)
            """)
            await conn.execute("""
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan VARCHAR(20) DEFAULT 'starter'
            """)
            await conn.execute("""
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS owner_user_id UUID REFERENCES users(id) ON DELETE SET NULL
            """)
            await conn.execute("""
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT false
            """)
            await conn.execute("""
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'America/Argentina/Buenos_Aires'
            """)
            await conn.execute("""
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'es-AR'
            """)
            await conn.execute("""
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'ARS'
            """)
            results.append("Extended tenants table")
            
            # 4. Add auth_provider to users
            await conn.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) DEFAULT 'whatsapp'
            """)
            await conn.execute("""
                UPDATE users SET auth_provider = 'google' WHERE phone LIKE 'oauth:%'
            """)
            results.append("Added auth_provider to users")
            
            # 5. Update existing tenant
            await conn.execute("""
                UPDATE tenants 
                SET 
                    home_name = COALESCE(home_name, 'Mi Hogar'),
                    onboarding_completed = true,
                    plan = 'family'
                WHERE id = '00000000-0000-0000-0000-000000000001'
            """)
            results.append("Updated existing tenant")
            
            # 6. Get user ID and set as owner
            user_row = await conn.fetchrow("""
                SELECT id FROM users 
                WHERE tenant_id = '00000000-0000-0000-0000-000000000001' 
                ORDER BY created_at ASC LIMIT 1
            """)
            
            if user_row:
                user_id = user_row["id"]
                await conn.execute("""
                    UPDATE users SET role = 'owner' WHERE id = $1
                """, user_id)
                await conn.execute("""
                    UPDATE tenants SET owner_user_id = $1 
                    WHERE id = '00000000-0000-0000-0000-000000000001'
                """, user_id)
                results.append(f"Set user {user_id} as owner")
            
            # 7. Register phone number
            await conn.execute("""
                INSERT INTO phone_tenant_mapping (phone, tenant_id, display_name, is_primary, verified_at)
                VALUES ($1, '00000000-0000-0000-0000-000000000001', $2, true, NOW())
                ON CONFLICT (phone) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    is_primary = EXCLUDED.is_primary,
                    verified_at = EXCLUDED.verified_at
            """, phone, name)
            results.append(f"Registered phone {phone}")
            
            # 8. Create trigger for updated_at
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_phone_tenant_mapping_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
            """)
            await conn.execute("""
                DROP TRIGGER IF EXISTS update_phone_tenant_mapping_updated_at ON phone_tenant_mapping
            """)
            await conn.execute("""
                CREATE TRIGGER update_phone_tenant_mapping_updated_at
                    BEFORE UPDATE ON phone_tenant_mapping
                    FOR EACH ROW
                    EXECUTE FUNCTION update_phone_tenant_mapping_updated_at()
            """)
            results.append("Created trigger")
            
        return {
            "success": True,
            "message": "Migration completed successfully",
            "results": results,
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": results,
        }
