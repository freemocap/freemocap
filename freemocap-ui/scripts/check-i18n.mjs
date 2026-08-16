import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const uiRoot = process.cwd();
const sourceRoot = path.join(uiRoot, "src");
const localeRoot = path.join(sourceRoot, "i18n", "locales");
const englishPath = path.join(localeRoot, "en-english.json");
const chinesePath = path.join(localeRoot, "zh-CN-zhongwen.json");

const allowedVisibleLiterals = new Set([
  "Blender",
  "CUDA",
  "FABRIK",
  "FreeMoCap",
  "FreeMocap",
  "FPS",
  "HH:MM:SS:FF",
  "ai-generated",
  "human-validated",
  "px",
  "/mm",
  "ChArUco",
  "Hz",
  "MediaPipe",
  "ONNX Runtime",
  "TensorRT",
  "TOML",
  "WebSocket",
  "Websocket",
  "AUTO",
  "MANUAL",
  "annotated",
  "auto",
  "backend",
  "custom",
  "frontend",
  "full",
  "heavy",
  "human-authored",
  "lite",
  "mediapipe",
  "playback",
  "posthoc",
  "realtime",
  "rtmpose",
  "synchronized",
  "string",
  "fps",
  "ms",
]);

const visibleAttributeNames = new Set([
  "alt",
  "aria-label",
  "buttonText",
  "description",
  "emptyText",
  "helperText",
  "label",
  "placeholder",
  "text",
  "title",
  "tooltip",
  "tooltipText",
]);

const visiblePropertyNames = new Set([
  "description",
  "emptyText",
  "helperText",
  "label",
  "message",
  "placeholder",
  "subtitle",
  "text",
  "title",
  "tooltip",
  "tooltipText",
]);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function flattenLeaves(value, prefix = "", leaves = new Map()) {
  for (const [key, child] of Object.entries(value)) {
    if (key === "_meta") continue;
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === "object" && !Array.isArray(child)) {
      flattenLeaves(child, fullKey, leaves);
    } else {
      leaves.set(fullKey, String(child));
    }
  }
  return leaves;
}

function placeholders(value) {
  return [...value.matchAll(/{{\s*([^}]+?)\s*}}/g)]
    .map((match) => match[1])
    .sort();
}

function walk(directory, extensions) {
  const files = [];
  for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(fullPath, extensions));
    } else if (extensions.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }
  return files;
}

function normalizeVisibleText(value) {
  return value.replace(/\s+/g, " ").trim();
}

function containsEnglishWords(value) {
  return /[A-Za-z]{2,}/.test(value);
}

function isAllowedVisibleLiteral(value) {
  if (allowedVisibleLiterals.has(value)) return true;
  if (/^(?:FreeMoCap|MediaPipe|RTMPose|YOLOX)(?:\s+[A-Za-z0-9.+-]+)*$/.test(value)) {
    return true;
  }
  return false;
}

function propertyName(node) {
  if (ts.isIdentifier(node) || ts.isStringLiteral(node)) return node.text;
  return null;
}

function stringValue(node) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    return node.text;
  }
  return null;
}

function calledFunctionName(expression) {
  if (ts.isIdentifier(expression)) return expression.text;
  if (ts.isPropertyAccessExpression(expression)) return expression.name.text;
  return null;
}

function isTranslationCall(node) {
  return ts.isCallExpression(node) && calledFunctionName(node.expression) === "t";
}

function location(sourceFile, node) {
  const position = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
  return `${path.relative(uiRoot, sourceFile.fileName)}:${position.line + 1}`;
}

function isNestedVisibleAttributeLiteral(node) {
  let current = node.parent;
  while (current) {
    if (ts.isCallExpression(current)) {
      const expression = current.expression;
      const isTranslationCall =
        (ts.isIdentifier(expression) && expression.text === "t") ||
        (ts.isPropertyAccessExpression(expression) && expression.name.text === "t");
      if (isTranslationCall) return false;
    }
    if (
      ts.isJsxExpression(current) &&
      current.parent &&
      (ts.isJsxElement(current.parent) || ts.isJsxFragment(current.parent))
    ) {
      return true;
    }
    if (ts.isJsxAttribute(current)) {
      return visibleAttributeNames.has(current.name.text);
    }
    if (ts.isJsxElement(current) || ts.isJsxSelfClosingElement(current)) return false;
    current = current.parent;
  }
  return false;
}

const english = flattenLeaves(readJson(englishPath));
const chinese = flattenLeaves(readJson(chinesePath));
const failures = [];

const missingChinese = [...english.keys()].filter((key) => !chinese.has(key));
const extraChinese = [...chinese.keys()].filter((key) => !english.has(key));
if (missingChinese.length) {
  failures.push(`Chinese locale is missing ${missingChinese.length} keys:\n  ${missingChinese.join("\n  ")}`);
}
if (extraChinese.length) {
  failures.push(`Chinese locale has ${extraChinese.length} extra keys:\n  ${extraChinese.join("\n  ")}`);
}

for (const key of [...english.keys()].filter((candidate) => chinese.has(candidate))) {
  const expected = placeholders(english.get(key));
  const actual = placeholders(chinese.get(key));
  if (JSON.stringify(expected) !== JSON.stringify(actual)) {
    failures.push(
      `Placeholder mismatch for "${key}": English [${expected.join(", ")}], Chinese [${actual.join(", ")}]`
    );
  }
}

const sourceFiles = walk(sourceRoot, new Set([".ts", ".tsx"]));
const translationReferences = new Map();
const visibleLiterals = new Map();

for (const filePath of sourceFiles) {
  const sourceText = fs.readFileSync(filePath, "utf8");
  const sourceFile = ts.createSourceFile(
    filePath,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    filePath.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  );

  function recordVisibleLiteral(node, rawValue) {
    const value = normalizeVisibleText(rawValue);
    if (!value || !containsEnglishWords(value) || isAllowedVisibleLiteral(value)) return;
    const key = `${filePath}:${node.getStart(sourceFile)}:${value}`;
    visibleLiterals.set(key, `${location(sourceFile, node)} — ${JSON.stringify(value)}`);
  }

  function recordVisibleErrorValue(node) {
    if (isTranslationCall(node)) return;
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      recordVisibleLiteral(node, node.text);
      return;
    }
    if (ts.isTemplateExpression(node)) {
      const value = [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join("");
      recordVisibleLiteral(node, value);
      return;
    }
    ts.forEachChild(node, recordVisibleErrorValue);
  }

  function visit(node) {
    if (ts.isCallExpression(node)) {
      const expression = node.expression;
      const translationCall = isTranslationCall(node);
      const key = node.arguments.length ? stringValue(node.arguments[0]) : null;
      if (translationCall && key) {
        translationReferences.set(key, location(sourceFile, node));
      }
      const functionName = calledFunctionName(expression);
      if (functionName && /^set(?:[A-Za-z]+)?Error$/.test(functionName)) {
        for (const argument of node.arguments) recordVisibleErrorValue(argument);
      }
    }

    if (filePath.endsWith(".tsx")) {
      if (ts.isJsxText(node)) {
        recordVisibleLiteral(node, node.text);
      } else if (ts.isJsxAttribute(node) && visibleAttributeNames.has(node.name.text)) {
        const initializer = node.initializer;
        if (initializer && ts.isStringLiteral(initializer)) {
          recordVisibleLiteral(initializer, initializer.text);
        } else if (
          initializer &&
          ts.isJsxExpression(initializer) &&
          initializer.expression
        ) {
          const value = stringValue(initializer.expression);
          if (value !== null) recordVisibleLiteral(initializer.expression, value);
        }
      } else if (
        ts.isPropertyAssignment(node) &&
        visiblePropertyNames.has(propertyName(node.name) ?? "")
      ) {
        const value = stringValue(node.initializer);
        if (value !== null) recordVisibleLiteral(node.initializer, value);
      } else if (
        (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
        (ts.isJsxExpression(node.parent) || isNestedVisibleAttributeLiteral(node))
      ) {
        recordVisibleLiteral(node, node.text);
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
}

const missingEnglishReferences = [...translationReferences.entries()]
  .filter(([key]) => !english.has(key))
  .map(([key, source]) => `${source} — ${key}`);
if (missingEnglishReferences.length) {
  failures.push(
    `Code references ${missingEnglishReferences.length} keys missing from English:\n  ${missingEnglishReferences.join("\n  ")}`
  );
}

const menuActionsPath = path.join(sourceRoot, "hooks", "useMenuActions.ts");
const menuActions = fs.readFileSync(menuActionsPath, "utf8");
const menuBlock = menuActions.match(/const MENU_LABEL_KEYS = \[([\s\S]*?)] as const;/);
if (menuBlock) {
  const menuKeys = [...menuBlock[1].matchAll(/['"]([^'"]+)['"]/g)].map((match) => match[1]);
  const missingMenuKeys = menuKeys.filter((key) => !english.has(key));
  if (missingMenuKeys.length) {
    failures.push(`Native menu references missing English keys:\n  ${missingMenuKeys.join("\n  ")}`);
  }
}

if (visibleLiterals.size) {
  failures.push(
    `Found ${visibleLiterals.size} unlocalized visible English literals:\n  ${[...visibleLiterals.values()].join("\n  ")}`
  );
}

if (failures.length) {
  console.error(failures.join("\n\n"));
  process.exitCode = 1;
} else {
  console.log(
    `i18n checks passed: ${english.size} English keys, ${chinese.size} Chinese keys, ${translationReferences.size} referenced keys.`
  );
}
