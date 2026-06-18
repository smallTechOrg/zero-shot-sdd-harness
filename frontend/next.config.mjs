/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export → plain HTML/CSS/JS in `out/`, served by FastAPI at :8001 (one process).
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
