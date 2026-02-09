/**
 * Generate a service token for homeai-assis to call homeai-api.
 * 
 * Usage:
 *   node scripts/generate_service_token.js <JWT_SECRET_KEY> <TENANT_ID>
 * 
 * Example:
 *   node scripts/generate_service_token.js "my-secret-key" "00000000-0000-0000-0000-000000000001"
 */

const jwt = require('jsonwebtoken');

function generateServiceToken(jwtSecret, tenantId, serviceName = 'homeai-assis') {
  const payload = {
    sub: `service-${serviceName}`,
    tenant_id: tenantId,
    role: 'system',
    type: 'service',
  };
  
  // Token expires in 1 year
  const options = {
    expiresIn: '365d',
    algorithm: 'HS256',
  };
  
  return jwt.sign(payload, jwtSecret, options);
}

function main() {
  const args = process.argv.slice(2);
  
  if (args.length < 2) {
    console.log(`
Usage: node scripts/generate_service_token.js <JWT_SECRET_KEY> <TENANT_ID>

Arguments:
  JWT_SECRET_KEY  - The JWT secret from homeai-api (Railway homeAssistant-backend)
  TENANT_ID       - The default tenant ID (from homeai-assis DEFAULT_TENANT_ID)

Example:
  node scripts/generate_service_token.js "my-secret-key" "00000000-0000-0000-0000-000000000001"
`);
    process.exit(1);
  }
  
  const jwtSecret = args[0];
  const tenantId = args[1];
  const serviceName = args[2] || 'homeai-assis';
  
  const token = generateServiceToken(jwtSecret, tenantId, serviceName);
  
  console.log('\n' + '='.repeat(60));
  console.log('SERVICE TOKEN GENERATED');
  console.log('='.repeat(60));
  console.log(`\nService: ${serviceName}`);
  console.log(`Tenant ID: ${tenantId}`);
  console.log(`Expires: 1 year from now`);
  console.log('\nToken:');
  console.log('-'.repeat(60));
  console.log(token);
  console.log('-'.repeat(60));
  console.log('\nNext steps:');
  console.log('1. Go to Railway dashboard');
  console.log('2. Select homeai-assis service');
  console.log('3. Go to Variables');
  console.log('4. Set BACKEND_API_KEY = <token above>');
  console.log('5. Redeploy the service');
  console.log('='.repeat(60));
}

main();
