// CloudBase 云托管 / 本地直连的统一传输层。
const config = require('./config.js');

let cloudInitialized = false;
const mediaCache = new Map();

function runtime() {
  if (typeof config.getApiRuntime === 'function') return config.getApiRuntime();
  // 兼容测试和旧的自定义 config：未声明云托管时继续使用直连。
  return {
    mode: config.apiTransport || 'direct',
    apiBase: config.apiBase || '',
    cloud: config.cloud || {},
  };
}

function isAbsoluteUrl(url) {
  return /^https?:\/\//i.test(url || '');
}

function cloudPath(url, current) {
  const value = String(url || '');
  const prefix = String((current.cloud && current.cloud.apiPrefix) || '').replace(/\/$/, '');
  if (prefix && (value === prefix || value.startsWith(`${prefix}/`))) return value;
  const suffix = value.startsWith('/') ? value : `/${value}`;
  return `${prefix}${suffix}` || '/';
}

function directUrl(url, current) {
  if (isAbsoluteUrl(url)) return url;
  const base = String(current.apiBase || '').replace(/\/$/, '');
  if (!base) throw new Error('本地接口地址未配置');
  return `${base}${String(url || '').startsWith('/') ? '' : '/'}${url || ''}`;
}

function initCloud() {
  const current = runtime();
  if (current.mode !== 'cloud') return false;
  if (!wx.cloud || typeof wx.cloud.init !== 'function' || typeof wx.cloud.callContainer !== 'function') {
    throw new Error('当前微信基础库不支持云托管，请升级微信后重试');
  }
  if (!cloudInitialized) {
    wx.cloud.init({ env: current.cloud.envId, traceUser: true });
    cloudInitialized = true;
  }
  return true;
}

function finishPromise(promise, success, fail, complete) {
  Promise.resolve(promise).then(
    (result) => {
      if (success) success(result);
      if (complete) complete(result);
    },
    (error) => {
      if (fail) fail(error);
      if (complete) complete(error);
    }
  );
  return promise;
}

function send(options) {
  const current = runtime();
  const url = options.url || '';
  if (current.mode !== 'cloud' || isAbsoluteUrl(url)) {
    let resolved;
    try { resolved = directUrl(url, current); }
    catch (error) {
      if (options.fail) options.fail(error);
      if (options.complete) options.complete(error);
      return null;
    }
    return wx.request({ ...options, url: resolved });
  }

  try { initCloud(); }
  catch (error) {
    if (options.fail) options.fail(error);
    if (options.complete) options.complete(error);
    return null;
  }

  const header = {
    ...(options.header || {}),
    'X-WX-SERVICE': current.cloud.service,
  };
  const promise = wx.cloud.callContainer({
    config: { env: current.cloud.envId },
    path: cloudPath(url, current),
    method: options.method || 'GET',
    data: options.data,
    header,
    timeout: options.timeout,
    dataType: options.dataType,
    responseType: options.responseType,
  });
  return finishPromise(promise, options.success, options.fail, options.complete);
}

function utf8(value) {
  const encoded = unescape(encodeURIComponent(String(value)));
  const bytes = new Uint8Array(encoded.length);
  for (let i = 0; i < encoded.length; i += 1) bytes[i] = encoded.charCodeAt(i);
  return bytes;
}

function concatBytes(parts) {
  const size = parts.reduce((total, part) => total + part.byteLength, 0);
  const result = new Uint8Array(size);
  let offset = 0;
  parts.forEach((part) => {
    result.set(part, offset);
    offset += part.byteLength;
  });
  return result.buffer;
}

function fileName(path) {
  const value = String(path || '').split(/[\\/]/).pop() || 'upload.jpg';
  return value.replace(/["\r\n]/g, '_');
}

function imageType(path) {
  const ext = (String(path || '').match(/\.([a-z0-9]+)(?:\?|$)/i) || [])[1];
  if (/^png$/i.test(ext || '')) return 'image/png';
  if (/^webp$/i.test(ext || '')) return 'image/webp';
  return 'image/jpeg';
}

function multipartBody(filePath, fieldName, formData, boundary, fileBuffer) {
  const parts = [];
  Object.keys(formData || {}).forEach((key) => {
    const safeKey = key.replace(/["\r\n]/g, '_');
    parts.push(utf8(`--${boundary}\r\nContent-Disposition: form-data; name="${safeKey}"\r\n\r\n${formData[key]}\r\n`));
  });
  parts.push(utf8(
    `--${boundary}\r\nContent-Disposition: form-data; name="${fieldName}"; filename="${fileName(filePath)}"\r\n` +
    `Content-Type: ${imageType(filePath)}\r\n\r\n`
  ));
  parts.push(new Uint8Array(fileBuffer));
  parts.push(utf8(`\r\n--${boundary}--\r\n`));
  return concatBytes(parts);
}

function uploadFile(options) {
  const current = runtime();
  const url = options.url || '';
  if (current.mode !== 'cloud' || isAbsoluteUrl(url)) {
    let resolved;
    try { resolved = directUrl(url, current); }
    catch (error) {
      if (options.fail) options.fail(error);
      if (options.complete) options.complete(error);
      return null;
    }
    return wx.uploadFile({ ...options, url: resolved });
  }

  const promise = new Promise((resolve, reject) => {
    const fs = wx.getFileSystemManager && wx.getFileSystemManager();
    if (!fs || !fs.readFile) {
      reject(new Error('当前微信版本不支持读取待上传图片'));
      return;
    }
    fs.readFile({
      filePath: options.filePath,
      success: ({ data }) => {
        const boundary = `----cdc${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
        const body = multipartBody(
          options.filePath,
          options.name || 'file',
          options.formData || {},
          boundary,
          data
        );
        send({
          url,
          method: 'POST',
          data: body,
          timeout: options.timeout,
          header: {
            ...(options.header || {}),
            'content-type': `multipart/form-data; boundary=${boundary}`,
          },
          success: (response) => {
            resolve({
              ...response,
              data: typeof response.data === 'string' ? response.data : JSON.stringify(response.data),
            });
          },
          fail: reject,
        });
      },
      fail: reject,
    });
  });
  return finishPromise(promise, options.success, options.fail, options.complete);
}

function getDirectBaseUrl() {
  const current = runtime();
  return current.mode === 'direct' ? String(current.apiBase || '').replace(/\/api\/v1\/?$/, '') : '';
}

function directlyDisplayable(url) {
  return /^(https?:|wxfile:|cloud:|data:)/i.test(url || '') || String(url || '').startsWith('//');
}

function mediaFileName(url) {
  const stable = String(url || '').split('?')[0];
  let hash = 2166136261;
  for (let i = 0; i < stable.length; i += 1) {
    hash ^= stable.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return `cdc-media-${(hash >>> 0).toString(16)}.jpg`;
}

function resolveMediaUrl(url) {
  if (!url) return Promise.resolve('');
  if (String(url).startsWith('//')) return Promise.resolve(`https:${url}`);
  if (directlyDisplayable(url)) return Promise.resolve(url);

  const current = runtime();
  if (current.mode !== 'cloud') {
    const base = getDirectBaseUrl();
    return Promise.resolve(`${base}${String(url).startsWith('/') ? '' : '/'}${url}`);
  }
  if (mediaCache.has(url)) return mediaCache.get(url);

  const pending = new Promise((resolve, reject) => {
    send({
      url,
      method: 'GET',
      responseType: 'arraybuffer',
      success: (response) => {
        if (response.statusCode < 200 || response.statusCode >= 300 || !(response.data instanceof ArrayBuffer)) {
          reject(new Error('图片暂时无法读取'));
          return;
        }
        const fs = wx.getFileSystemManager && wx.getFileSystemManager();
        const root = wx.env && wx.env.USER_DATA_PATH;
        if (!fs || !fs.writeFile || !root) {
          reject(new Error('当前微信版本不支持图片缓存'));
          return;
        }
        const filePath = `${root}/${mediaFileName(url)}`;
        fs.writeFile({ filePath, data: response.data, success: () => resolve(filePath), fail: reject });
      },
      fail: reject,
    });
  }).catch((error) => {
    mediaCache.delete(url);
    throw error;
  });
  mediaCache.set(url, pending);
  return pending;
}

module.exports = { send, uploadFile, initCloud, getDirectBaseUrl, resolveMediaUrl };
