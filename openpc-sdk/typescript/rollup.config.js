import typescript from '@rollup/plugin-typescript';

export default {
  input: 'src/index.ts',
  output: [
    {
      file: 'dist/index.mjs',
      format: 'es',
      sourcemap: true,
    },
    {
      file: 'dist/index.js',
      format: 'cjs',
      sourcemap: true,
    },
  ],
  plugins: [typescript()],
  external: [],
};
