/** @type {import('next').NextConfig} */
// Console de operação local (roda na máquina do gestor da vitrine), sem exposição
// externa na v1. Não há build estático das páginas que leem o Registro — elas são
// dinâmicas (force-dynamic), lidas a cada request.
const nextConfig = { reactStrictMode: true };
export default nextConfig;
