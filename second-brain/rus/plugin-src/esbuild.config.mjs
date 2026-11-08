// Сборка плагина: src/main.ts → <папка программы>/plugin/main.js (+ manifest.json, styles.css рядом).
// В архиве программы исходники лежат в plugin-src, собранный плагин — в соседней папке plugin.
// Другую папку можно передать аргументом: node esbuild.config.mjs <папка>
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
  banner: { js: "/* Второй мозг — плагин Obsidian. Исходники: папка plugin-src в архиве программы. */" },
});
copyFileSync("manifest.json", `${out}/manifest.json`);
copyFileSync("styles.css", `${out}/styles.css`);
