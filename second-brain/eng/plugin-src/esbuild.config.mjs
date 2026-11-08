// Plugin assembly: src/main.ts → <program-folder>/plugin/main.js (+ manifest.json, styles.css near).
// The programs archives contain the source codes in plugin-src, assembled plugin — next-door plugin.
// Another folder can be transmitted by argument.: node esbuild.config.mjs <folder>
import esbuild from "esbuild";
import { builtinModules } from "node:module";
import { copyFileSync, existsSync, mkdirSync } from "node:fs";

const out = process.argv[2] || (existsSync("../brain/__main__.py") ? "../plugin" : "../app/plugin");
mkdirSync(out, { recursive: true });
await esbuild.build({
  entryPoints: ["src/main.ts"],
  bundle: true,
  format: "cjs",
  target: "es2020",
  outfile: `${out}/main.js`,
  external: ["obsidian", "electron", "@codemirror/*", "@lezer/*", ...builtinModules, ...builtinModules.map((m) => `node:${m}`)],
  logLevel: "info",
  legalComments: "none",
  banner: { js: "/* Second Brain — plugin Obsidian. Sources: folder plugin-src program-archive. */" },
});
copyFileSync("manifest.json", `${out}/manifest.json`);
copyFileSync("styles.css", `${out}/styles.css`);
