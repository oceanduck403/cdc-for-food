#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const DEFAULT_LOCAL_CONFIG = path.join(__dirname, 'miniprogram.local.json');
const DEFAULT_OUTPUT = path.join(REPO_ROOT, 'build', 'wechat-release');

function fail(message) {
  const error = new Error(message);
  error.name = 'ReleaseConfigError';
  throw error;
}

function parseArgs(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const name = argv[index];
    if (!['--api-base', '--config', '--output', '--validate'].includes(name)) {
      fail(`未知参数：${name}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) fail(`${name} 缺少参数值`);
    index += 1;
    if (name === '--api-base') options.apiBase = value;
    if (name === '--config') options.configPath = path.resolve(value);
    if (name === '--output') options.outputDir = path.resolve(value);
    if (name === '--validate') options.validateDir = path.resolve(value);
  }
  return options;
}

function validateApiBase(value) {
  const raw = String(value || '').trim();
  if (!raw) fail('未配置 apiBase；请填写本机配置文件、CDC_MINIPROGRAM_API_BASE 或 --api-base');
  if (/(__FILL|YOUR_|PLACEHOLDER|\{\{|\}\})/i.test(raw)) fail('apiBase 仍含占位符');

  let parsed;
  try { parsed = new URL(raw); }
  catch (_) { fail('apiBase 必须是完整 URL'); }

  if (parsed.protocol !== 'https:') fail('apiBase 必须使用 HTTPS');
  if (parsed.username || parsed.password) fail('apiBase 不能包含账号或密码');
  if (parsed.search || parsed.hash) fail('apiBase 不能包含查询参数或片段');
  if (parsed.port && parsed.port !== '443') fail('apiBase 不能使用非 443 端口');

  const hostname = parsed.hostname.toLowerCase().replace(/\.$/, '');
  const addressCandidate = hostname.replace(/^\[|\]$/g, '');
  if (!hostname || net.isIP(addressCandidate)) fail('apiBase 必须使用已备案的域名，不能使用 IP 地址');
  if (!hostname.includes('.') || hostname === 'localhost' || hostname.endsWith('.local')) {
    fail('apiBase 必须使用公网域名');
  }
  if (/(^|\.)(example|invalid|test)(\.|$)/i.test(hostname) || /^(your-|your\.)/i.test(hostname)) {
    fail('apiBase 仍是示例域名或占位域名');
  }

  const pathname = parsed.pathname.replace(/\/+$/, '');
  if (!pathname.endsWith('/api/v1')) fail('apiBase 路径必须以 /api/v1 结尾');
  if (pathname.includes('//')) fail('apiBase 路径不能包含连续斜杠');
  return `https://${hostname}${pathname}`;
}

function readConfig(configPath) {
  if (!fs.existsSync(configPath)) return {};
  let value;
  try { value = JSON.parse(fs.readFileSync(configPath, 'utf8').replace(/^\uFEFF/, '')); }
  catch (error) { fail(`无法读取小程序发布配置：${error.message}`); }
  if (!value || Array.isArray(value) || typeof value !== 'object') fail('小程序发布配置必须是 JSON 对象');
  return value;
}

function resolveApiBase(options = {}) {
  const configPath = options.configPath || DEFAULT_LOCAL_CONFIG;
  const local = readConfig(configPath);
  return validateApiBase(options.apiBase || process.env.CDC_MINIPROGRAM_API_BASE || local.apiBase);
}

function runtimeSource(apiBase) {
  return [
    '// 此文件由 deploy/selfhost/build_miniprogram.js 生成，请勿手工修改。',
    'module.exports = Object.freeze({',
    '  generated: true,',
    "  apiTransport: 'direct',",
    `  apiBase: ${JSON.stringify(apiBase)},`,
    '  cloud: Object.freeze({ envId: \'\', service: \'\', apiPrefix: \'/api/v1\' }),',
    '});',
    '',
  ].join(os.EOL);
}

function loadRuntime(runtimePath) {
  const resolved = require.resolve(runtimePath);
  delete require.cache[resolved];
  return require(resolved);
}

function validateRelease(outputDir) {
  const projectPath = path.join(outputDir, 'project.config.json');
  const runtimePath = path.join(outputDir, 'miniprogram', 'utils', 'release-runtime.js');
  const configPath = path.join(outputDir, 'miniprogram', 'utils', 'config.js');
  for (const required of [projectPath, runtimePath, configPath]) {
    if (!fs.existsSync(required)) fail(`发布产物缺少文件：${path.relative(outputDir, required)}`);
  }

  const project = JSON.parse(fs.readFileSync(projectPath, 'utf8').replace(/^\uFEFF/, ''));
  if (project.miniprogramRoot !== 'miniprogram/') fail('发布产物 miniprogramRoot 必须为 miniprogram/');
  if (!/^wx[A-Za-z0-9]{10,30}$/.test(String(project.appid || ''))) fail('发布产物 AppID 未配置或格式异常');

  const runtime = loadRuntime(runtimePath);
  if (runtime.generated !== true || runtime.apiTransport !== 'direct') {
    fail('发布产物未注入 direct 传输配置');
  }
  const normalized = validateApiBase(runtime.apiBase);
  if (runtime.apiBase !== normalized) fail('发布产物 apiBase 未规范化');

  const source = fs.readFileSync(configPath, 'utf8');
  if (!/const useMock = false;/.test(source)) fail('正式包必须关闭 mock 数据');
  return { apiBase: normalized, appid: project.appid };
}

function buildRelease(options = {}) {
  const repoRoot = options.repoRoot || REPO_ROOT;
  const outputDir = options.outputDir || DEFAULT_OUTPUT;
  const apiBase = resolveApiBase(options);
  const sourceMiniProgram = path.join(repoRoot, 'miniprogram');
  const sourceProject = path.join(repoRoot, 'project.config.json');
  if (!fs.existsSync(sourceMiniProgram) || !fs.existsSync(sourceProject)) fail('未找到小程序源码或 project.config.json');

  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });
  fs.cpSync(sourceMiniProgram, path.join(outputDir, 'miniprogram'), {
    recursive: true,
    filter: source => !/(^|[\\/])(tests|node_modules|miniprogram_npm)([\\/]|$)/.test(source),
  });
  fs.copyFileSync(sourceProject, path.join(outputDir, 'project.config.json'));
  fs.writeFileSync(
    path.join(outputDir, 'miniprogram', 'utils', 'release-runtime.js'),
    runtimeSource(apiBase),
    'utf8'
  );
  fs.writeFileSync(
    path.join(outputDir, 'release-manifest.json'),
    `${JSON.stringify({ generatedAt: new Date().toISOString(), apiBase }, null, 2)}${os.EOL}`,
    'utf8'
  );
  validateRelease(outputDir);
  return { outputDir, apiBase };
}

function main(argv = process.argv.slice(2)) {
  try {
    const options = parseArgs(argv);
    if (options.validateDir) {
      const checked = validateRelease(options.validateDir);
      console.log(`发布产物校验通过：${checked.apiBase}`);
      return 0;
    }
    const result = buildRelease(options);
    console.log(`小程序发布包已生成：${result.outputDir}`);
    console.log(`正式 API：${result.apiBase}`);
    console.log('请在微信开发者工具中导入该目录；不要直接上传源码目录。');
    return 0;
  } catch (error) {
    console.error(`小程序发布包生成失败：${error.message}`);
    return 1;
  }
}

if (require.main === module) process.exitCode = main();

module.exports = {
  buildRelease,
  parseArgs,
  resolveApiBase,
  runtimeSource,
  validateApiBase,
  validateRelease,
};
