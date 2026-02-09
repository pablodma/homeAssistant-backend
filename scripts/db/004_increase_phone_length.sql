-- HomeAI Assistant - Migration 004
-- Aumentar longitud del campo phone para soportar OAuth users
-- Fecha: 2026-02-09

-- El campo phone se usaba solo para teléfonos (+5491123456789 = 14 chars)
-- Pero OAuth users usan "oauth:{email}" que puede exceder 20 chars
-- Aumentamos a 100 para soportar ambos casos

ALTER TABLE users ALTER COLUMN phone TYPE VARCHAR(100);

-- También necesitamos permitir phone NULL para usuarios OAuth puros
-- (en el futuro podríamos querer usuarios que solo tienen email)
-- ALTER TABLE users ALTER COLUMN phone DROP NOT NULL;

COMMENT ON COLUMN users.phone IS 'Phone number or OAuth placeholder (oauth:email)';
