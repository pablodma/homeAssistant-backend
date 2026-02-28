-- 020: Finance hierarchy (categories/subcategories) + incomes table
-- Adds parent_id, sort_order, is_system to budget_categories for fixed taxonomy.
-- Creates incomes table. Migrates existing flat categories to hierarchical structure.

BEGIN;

-- =============================================================================
-- 1. ALTER budget_categories: add hierarchy columns
-- =============================================================================

ALTER TABLE budget_categories
  ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES budget_categories(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS is_system BOOLEAN DEFAULT true;

-- Drop the old unique constraint and create the new one
ALTER TABLE budget_categories DROP CONSTRAINT IF EXISTS budget_categories_tenant_id_name_key;
ALTER TABLE budget_categories ADD CONSTRAINT budget_categories_tenant_parent_name_key UNIQUE (tenant_id, parent_id, name);

CREATE INDEX IF NOT EXISTS idx_budget_cat_parent ON budget_categories(parent_id);

-- =============================================================================
-- 2. CREATE TABLE incomes
-- =============================================================================

CREATE TABLE IF NOT EXISTS incomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) DEFAULT 'ARS',
    description TEXT,
    income_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    idempotency_key VARCHAR(100),
    UNIQUE(tenant_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_incomes_tenant_date ON incomes(tenant_id, income_date);

ALTER TABLE incomes ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_incomes' AND tablename = 'incomes') THEN
    EXECUTE 'CREATE POLICY tenant_isolation_incomes ON incomes USING (tenant_id = current_setting(''app.current_tenant_id'', true)::uuid)';
  END IF;
END $$;

COMMENT ON TABLE incomes IS 'Ingresos registrados por tenant';

-- =============================================================================
-- 3. Seed fixed taxonomy for ALL existing tenants
-- =============================================================================

-- Helper function to seed the full taxonomy for a single tenant.
-- Handles mapping of old flat categories to new subcategories.
CREATE OR REPLACE FUNCTION _seed_taxonomy_for_tenant(_tid UUID) RETURNS void AS $$
DECLARE
    _group_id UUID;
    _sub_id UUID;
    _old_id UUID;
BEGIN
    -- =========================================================================
    -- Alimentación (sort 1)
    -- =========================================================================
    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system, monthly_limit)
    VALUES (_tid, 'Alimentación', NULL, 1, true, 0)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING
    RETURNING id INTO _group_id;
    IF _group_id IS NULL THEN
        SELECT id INTO _group_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Alimentación' AND parent_id IS NULL;
    END IF;

    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system) VALUES
        (_tid, 'Restaurantes y delivery', _group_id, 1, true),
        (_tid, 'Supermercado', _group_id, 2, true),
        (_tid, 'Otros (Alimentación)', _group_id, 3, true)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING;

    -- Remap old "Supermercado" -> new subcategory
    SELECT id INTO _old_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Supermercado' AND parent_id IS NULL;
    IF _old_id IS NOT NULL THEN
        SELECT id INTO _sub_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Supermercado' AND parent_id = _group_id;
        IF _sub_id IS NOT NULL THEN
            UPDATE expenses SET category_id = _sub_id WHERE category_id = _old_id AND tenant_id = _tid;
            DELETE FROM budget_categories WHERE id = _old_id;
        END IF;
    END IF;

    -- =========================================================================
    -- Bienestar (sort 2)
    -- =========================================================================
    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system, monthly_limit)
    VALUES (_tid, 'Bienestar', NULL, 2, true, 0)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING
    RETURNING id INTO _group_id;
    IF _group_id IS NULL THEN
        SELECT id INTO _group_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Bienestar' AND parent_id IS NULL;
    END IF;

    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system) VALUES
        (_tid, 'Cuidado Personal', _group_id, 1, true),
        (_tid, 'Deporte', _group_id, 2, true),
        (_tid, 'Educación', _group_id, 3, true),
        (_tid, 'Salud', _group_id, 4, true),
        (_tid, 'Otros (Bienestar)', _group_id, 5, true)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING;

    -- Remap old "Salud"
    SELECT id INTO _old_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Salud' AND parent_id IS NULL;
    IF _old_id IS NOT NULL THEN
        SELECT id INTO _sub_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Salud' AND parent_id = _group_id;
        IF _sub_id IS NOT NULL THEN
            UPDATE expenses SET category_id = _sub_id WHERE category_id = _old_id AND tenant_id = _tid;
            DELETE FROM budget_categories WHERE id = _old_id;
        END IF;
    END IF;

    -- Remap old "Educación"
    SELECT id INTO _old_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Educación' AND parent_id IS NULL;
    IF _old_id IS NOT NULL THEN
        SELECT id INTO _sub_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Educación' AND parent_id = _group_id;
        IF _sub_id IS NOT NULL THEN
            UPDATE expenses SET category_id = _sub_id WHERE category_id = _old_id AND tenant_id = _tid;
            DELETE FROM budget_categories WHERE id = _old_id;
        END IF;
    END IF;

    -- =========================================================================
    -- Compras (sort 3)
    -- =========================================================================
    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system, monthly_limit)
    VALUES (_tid, 'Compras', NULL, 3, true, 0)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING
    RETURNING id INTO _group_id;
    IF _group_id IS NULL THEN
        SELECT id INTO _group_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Compras' AND parent_id IS NULL;
    END IF;

    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system) VALUES
        (_tid, 'Electrónicos', _group_id, 1, true),
        (_tid, 'Hogar', _group_id, 2, true),
        (_tid, 'Mascotas', _group_id, 3, true),
        (_tid, 'Medicina', _group_id, 4, true),
        (_tid, 'Niños', _group_id, 5, true),
        (_tid, 'Suscripciones', _group_id, 6, true),
        (_tid, 'Vestimenta', _group_id, 7, true),
        (_tid, 'Otros (Compras)', _group_id, 8, true)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING;

    -- Remap old "Otros"
    SELECT id INTO _old_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Otros' AND parent_id IS NULL;
    IF _old_id IS NOT NULL THEN
        SELECT id INTO _sub_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Otros (Compras)' AND parent_id = _group_id;
        IF _sub_id IS NOT NULL THEN
            UPDATE expenses SET category_id = _sub_id WHERE category_id = _old_id AND tenant_id = _tid;
            DELETE FROM budget_categories WHERE id = _old_id;
        END IF;
    END IF;

    -- =========================================================================
    -- Movilidad (sort 4)
    -- =========================================================================
    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system, monthly_limit)
    VALUES (_tid, 'Movilidad', NULL, 4, true, 0)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING
    RETURNING id INTO _group_id;
    IF _group_id IS NULL THEN
        SELECT id INTO _group_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Movilidad' AND parent_id IS NULL;
    END IF;

    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system) VALUES
        (_tid, 'Apps de viajes', _group_id, 1, true),
        (_tid, 'Combustible', _group_id, 2, true),
        (_tid, 'Patente y seguro', _group_id, 3, true),
        (_tid, 'Transporte Público', _group_id, 4, true),
        (_tid, 'Otros (Movilidad)', _group_id, 5, true)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING;

    -- Remap old "Transporte"
    SELECT id INTO _old_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Transporte' AND parent_id IS NULL;
    IF _old_id IS NOT NULL THEN
        SELECT id INTO _sub_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Transporte Público' AND parent_id = _group_id;
        IF _sub_id IS NOT NULL THEN
            UPDATE expenses SET category_id = _sub_id WHERE category_id = _old_id AND tenant_id = _tid;
            DELETE FROM budget_categories WHERE id = _old_id;
        END IF;
    END IF;

    -- =========================================================================
    -- Obligaciones (sort 5)
    -- =========================================================================
    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system, monthly_limit)
    VALUES (_tid, 'Obligaciones', NULL, 5, true, 0)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING
    RETURNING id INTO _group_id;
    IF _group_id IS NULL THEN
        SELECT id INTO _group_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Obligaciones' AND parent_id IS NULL;
    END IF;

    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system) VALUES
        (_tid, 'Gastos laborales', _group_id, 1, true),
        (_tid, 'Servicios profesionales', _group_id, 2, true),
        (_tid, 'Trámites e impuestos', _group_id, 3, true),
        (_tid, 'Otros (Obligaciones)', _group_id, 4, true)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING;

    -- =========================================================================
    -- Recreación (sort 6)
    -- =========================================================================
    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system, monthly_limit)
    VALUES (_tid, 'Recreación', NULL, 6, true, 0)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING
    RETURNING id INTO _group_id;
    IF _group_id IS NULL THEN
        SELECT id INTO _group_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Recreación' AND parent_id IS NULL;
    END IF;

    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system) VALUES
        (_tid, 'Eventos', _group_id, 1, true),
        (_tid, 'Hobbies', _group_id, 2, true),
        (_tid, 'Vacaciones', _group_id, 3, true),
        (_tid, 'Otros (Recreación)', _group_id, 4, true)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING;

    -- Remap old "Entretenimiento"
    SELECT id INTO _old_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Entretenimiento' AND parent_id IS NULL;
    IF _old_id IS NOT NULL THEN
        SELECT id INTO _sub_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Hobbies' AND parent_id = _group_id;
        IF _sub_id IS NOT NULL THEN
            UPDATE expenses SET category_id = _sub_id WHERE category_id = _old_id AND tenant_id = _tid;
            DELETE FROM budget_categories WHERE id = _old_id;
        END IF;
    END IF;

    -- =========================================================================
    -- Vivienda (sort 7)
    -- =========================================================================
    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system, monthly_limit)
    VALUES (_tid, 'Vivienda', NULL, 7, true, 0)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING
    RETURNING id INTO _group_id;
    IF _group_id IS NULL THEN
        SELECT id INTO _group_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Vivienda' AND parent_id IS NULL;
    END IF;

    INSERT INTO budget_categories (tenant_id, name, parent_id, sort_order, is_system) VALUES
        (_tid, 'Alquiler', _group_id, 1, true),
        (_tid, 'Conectividad', _group_id, 2, true),
        (_tid, 'Servicios', _group_id, 3, true),
        (_tid, 'Otros (Vivienda)', _group_id, 4, true)
    ON CONFLICT (tenant_id, parent_id, name) DO NOTHING;

    -- Remap old "Servicios" (flat) -> subcategory under Vivienda
    SELECT id INTO _old_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Servicios' AND parent_id IS NULL;
    IF _old_id IS NOT NULL THEN
        SELECT id INTO _sub_id FROM budget_categories WHERE tenant_id = _tid AND name = 'Servicios' AND parent_id = _group_id;
        IF _sub_id IS NOT NULL THEN
            UPDATE expenses SET category_id = _sub_id WHERE category_id = _old_id AND tenant_id = _tid;
            DELETE FROM budget_categories WHERE id = _old_id;
        END IF;
    END IF;

    -- =========================================================================
    -- Remap any remaining custom categories to closest "Otros" subcategory
    -- =========================================================================
    -- Any flat categories (parent_id IS NULL, not a group) that weren't mapped above
    -- get their expenses moved to "Otros (Compras)" and then deleted.
    FOR _old_id IN
        SELECT bc.id FROM budget_categories bc
        WHERE bc.tenant_id = _tid
          AND bc.parent_id IS NULL
          AND bc.name NOT IN ('Alimentación','Bienestar','Compras','Movilidad','Obligaciones','Recreación','Vivienda')
    LOOP
        SELECT id INTO _sub_id FROM budget_categories
        WHERE tenant_id = _tid AND name = 'Otros (Compras)'
          AND parent_id IS NOT NULL
        LIMIT 1;

        IF _sub_id IS NOT NULL THEN
            UPDATE expenses SET category_id = _sub_id WHERE category_id = _old_id AND tenant_id = _tid;
        END IF;
        DELETE FROM budget_categories WHERE id = _old_id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Run seed for every existing tenant
DO $$
DECLARE
    _t RECORD;
BEGIN
    FOR _t IN SELECT id FROM tenants LOOP
        PERFORM _seed_taxonomy_for_tenant(_t.id);
    END LOOP;
END;
$$;

-- Clean up helper function
DROP FUNCTION IF EXISTS _seed_taxonomy_for_tenant(UUID);

COMMIT;
