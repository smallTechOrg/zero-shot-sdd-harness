import type { NextConfig } from 'next'

const config: NextConfig = {
  output: 'export',
  basePath: '/app',
  trailingSlash: true,
  images: { unoptimized: true },
  webpack: config => {
    // vega pulls in an optional `canvas` native module it never needs in the
    // browser (we render SVG). Stub it so the build doesn't emit a noisy warning.
    config.resolve = config.resolve ?? {}
    config.resolve.alias = { ...(config.resolve.alias ?? {}), canvas: false }
    return config
  },
}

export default config
