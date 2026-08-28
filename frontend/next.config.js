/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // Backend base URL comes from an env var so the same build works
  // locally (docker-compose) and on Vercel (pointed at the Railway API).
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};
