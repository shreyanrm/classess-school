/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@classess/design-system', '@classess/contracts'],
  webpack: (config) => {
    // The @classess/contracts source uses NodeNext-style explicit `.js`
    // specifiers on its relative imports (e.g. `./events/index.js`) while the
    // files on disk are TypeScript. tsc (Bundler resolution) maps these to
    // `.ts`; webpack does not by default. extensionAlias teaches webpack the
    // same mapping so the contracts package resolves from source — no rebuild
    // of the package required.
    config.resolve.extensionAlias = {
      ...(config.resolve.extensionAlias ?? {}),
      '.js': ['.ts', '.tsx', '.js', '.jsx'],
      '.mjs': ['.mts', '.mjs'],
    };
    return config;
  },
};

export default nextConfig;
