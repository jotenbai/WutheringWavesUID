const publicPrefix = (window.GALLERY_PUBLIC_PREFIX || "").replace(/\/$/, "");

const appEl = document.getElementById("app");
const authSlot = document.getElementById("auth-slot");
const navEl = document.getElementById("site-nav");

/** @type {object|null} */
let currentUser = null;
/** @type {boolean} */
let oauthConfigured = false;

/** @type {{ list: object[], index: number } | null} */
let lightboxState = null;
let lightboxKeyHandler = null;

function api(path, opts = {}) {
  return fetch(`${publicPrefix}/api${path}`, {
    credentials: "same-origin",
    ...opts,
  }).then(async (r) => {
    if (!r.ok) {
      let msg = r.statusText;
      try {
        const j = await r.json();
        msg = j.detail || JSON.stringify(j);
      } catch {
        try {
          msg = await r.text();
        } catch {
          /* ignore */
        }
      }
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    if (r.status === 204) return null;
    return r.json();
  });
}

function absUrl(url) {
  if (!url) return "";
  if (url.startsWith("http")) return url;
  return url.startsWith("/") ? url : `${publicPrefix}/${url}`;
}

function appHref(sub = "") {
  const root = publicPrefix || "";
  if (!sub) return root ? `${root}/` : "/";
  return `${root}/${String(sub).replace(/^\//, "")}`;
}

function pathParts() {
  let path = location.pathname;
  if (publicPrefix && path.startsWith(publicPrefix)) {
    path = path.slice(publicPrefix.length) || "/";
  }
  return path.split("/").filter(Boolean);
}

function migrateHashRoute() {
  const hash = location.hash.replace(/^#\/?/, "");
  if (!hash) return;
  history.replaceState(null, "", appHref(hash));
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/** ISO UTC → 浏览器当地时间，如 2026-09-13 10:31:02 */
function formatLocalTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function renderNav() {
  if (!navEl) return;
  const links = [
    { href: appHref(), label: "浏览", match: (p) => !p.length || p[0] === "char" },
    { href: appHref("submit"), label: "投稿", match: (p) => p[0] === "submit" },
    { href: appHref("me"), label: "我的投稿", match: (p) => p[0] === "me" },
  ];
  if (currentUser?.is_admin) {
    links.push({ href: appHref("review"), label: "审核", match: (p) => p[0] === "review" });
    links.push({ href: appHref("history"), label: "审核历史", match: (p) => p[0] === "history" });
  }
  const parts = pathParts();
  navEl.innerHTML = links
    .map((l) => {
      const on = l.match(parts) ? " is-active" : "";
      return `<a class="nav-link${on}" href="${l.href}" data-link>${l.label}</a>`;
    })
    .join("");
}

async function refreshAuth() {
  try {
    const data = await api("/me");
    oauthConfigured = Boolean(data.oauth_configured);
    currentUser = data.user;
    renderAuth(data);
    renderNav();
  } catch {
    currentUser = null;
    if (authSlot) authSlot.innerHTML = "";
    renderNav();
  }
}

function renderAuth(data) {
  if (!authSlot) return;
  const loginHref = `${publicPrefix}/auth/login`;
  const logoutHref = `${publicPrefix}/auth/logout`;
  if (!data.oauth_configured) {
    authSlot.innerHTML = `<div class="auth-box"><div class="auth-meta"><span class="role">登录未配置</span></div></div>`;
    return;
  }
  const u = data.user;
  if (!u) {
    authSlot.innerHTML = `
      <div class="auth-box">
        <div class="auth-meta">
          <span class="name">游客</span>
          <span class="role">可浏览已通过图集</span>
        </div>
        <div class="auth-actions">
          <a class="btn-auth" href="${loginHref}">Discord 登录</a>
        </div>
      </div>`;
    return;
  }
  const roleLabel =
    u.role === "admin" ? "管理员" : u.role === "user" ? "「守岸人」用户" : "已登录（未绑定）";
  const roleClass = u.role === "admin" ? "admin" : u.role === "user" ? "user" : "";
  let hint = "请先绑定 UID";
  if (u.role === "admin") hint = u.is_master ? "主人·可审核" : "可审核";
  else if (u.can_submit) hint = "可投稿";
  authSlot.innerHTML = `
    <div class="auth-box">
      ${u.avatar_url ? `<img src="${escapeHtml(u.avatar_url)}" alt="" />` : ""}
      <div class="auth-meta">
        <span class="name">${escapeHtml(u.display_name)}</span>
        <span class="role ${roleClass}">${roleLabel} · ${hint}</span>
      </div>
      <div class="auth-actions">
        <a class="btn-auth" href="${logoutHref}">退出</a>
      </div>
    </div>`;
}

function route() {
  closeLightbox(true);
  renderNav();
  const parts = pathParts();
  if (parts[0] === "char" && parts[1]) return renderChar(parts[1]);
  if (parts[0] === "submit") return renderSubmit();
  if (parts[0] === "me") return renderMySubmissions();
  if (parts[0] === "review") return renderReview();
  if (parts[0] === "history") return renderReviewHistory();
  return renderHome();
}

function helpGuest() {
  return `
    <div class="help-card">
      <h2>想投稿？</h2>
      <p>需要先成为<strong>「守岸人」用户</strong>：在任意已邀请「守岸人」机器人的 Discord 服务器（不一定是本服）里，对机器人完成 UID 绑定，再用本页右上角 Discord 登录。</p>
      <p>游客可以自由浏览已通过的图集。</p>
    </div>`;
}

function helpUnbound() {
  return `
    <div class="help-card">
      <h2>尚未绑定「守岸人」</h2>
      <p>你已登录 Discord，但本机没有 WavesBind 记录。请先到任意邀请了「守岸人」的服务器，对机器人绑定鸣潮 UID，再回来投稿。</p>
    </div>`;
}

function helpSubmitter() {
  return `
    <details class="help-card help-fold">
      <summary>投稿说明</summary>
      <ul>
        <li>选择角色，粘贴<strong>原图链接</strong>（任意可打开的作品页均可；尽量最大分辨率，避免审核裁成 9:16 后面板太糊）。</li>
        <li><strong>Pixiv 的情况</strong>：请用作品页 <code>https://www.pixiv.net/artworks/…</code>，不要用 <code>i.pximg.net</code> 直链（会 403）；多图作品在链接后加 <code>#N</code> 标明第几张（从 <strong>1</strong> 起：文件名 <code>_p0</code>→<code>#1</code>，<code>_p1</code>→<code>#2</code>，例如 <code>…/artworks/148785181#8</code>）。</li>
        <li>本图裁剪由管理员完成；通过后可在 Discord 用 <code>角色名面板图号</code> 指定立绘。</li>
      </ul>
    </details>`;
}

const ZIGZAG_MAP = [
   0,  1,  8, 16,  9,  2,  3, 10,
  17, 24, 32, 25, 18, 11,  4,  5,
  12, 19, 26, 33, 40, 48, 41, 34,
  27, 20, 13,  6,  7, 14, 21, 28,
  35, 42, 49, 56, 57, 50, 43, 36,
  29, 22, 15, 23, 30, 37, 44, 51,
  58, 59, 52, 45, 38, 31, 39, 46,
  53, 60, 61, 54, 47, 55, 62, 63,
];
const STD_LUMINANCE_QUANT = [
  16, 11, 10, 16, 24, 40, 51, 61,
  12, 12, 14, 19, 26, 58, 60, 55,
  14, 13, 16, 24, 40, 57, 69, 56,
  14, 17, 22, 29, 51, 87, 80, 62,
  18, 22, 37, 56, 68, 109, 103, 77,
  24, 35, 55, 64, 81, 104, 113, 92,
  49, 64, 78, 87, 103, 121, 120, 101,
  72, 92, 95, 98, 112, 100, 103, 99,
];

function estimateJpegQuality(u8) {
  let offset = 2;
  while (offset < u8.length - 1) {
    if (u8[offset] !== 0xff) {
      offset++;
      continue;
    }
    const marker = u8[offset + 1];
    offset += 2;
    if (marker === 0xd8 || marker === 0xd9 || marker === 0x00 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    if (offset + 2 > u8.length) break;
    const len = (u8[offset] << 8) | u8[offset + 1];
    if (marker === 0xdb) {
      let p = offset + 2;
      const end = offset + len;
      while (p < end) {
        const info = u8[p++];
        const tableId = info & 0x0f;
        const precision = (info >> 4) & 0x0f;
        const tlen = precision === 1 ? 128 : 64;
        if (tableId === 0 && p + tlen <= end) {
          const nat = new Array(64);
          for (let i = 0; i < 64; i++) {
            const val = precision === 1 ? ((u8[p + i * 2] << 8) | u8[p + i * 2 + 1]) : u8[p + i];
            nat[ZIGZAG_MAP[i]] = val;
          }
          let sum = 0;
          for (let i = 0; i < 64; i++) {
            sum += (nat[i] * 100.0) / STD_LUMINANCE_QUANT[i];
          }
          const scale = sum / 64.0;
          const q = scale <= 100 ? (200.0 - scale) / 2.0 : 5000.0 / scale;
          return Math.round(q);
        }
        p += tlen;
      }
    }
    offset += len;
  }
  return null;
}

async function validatePileFile(file) {
  const errors = [];
  if (!file) {
    return { ok: false, errors: ["请先选择文件"] };
  }

  // 1. 读取尺寸，严格校验宽高比 9:16 与宽度 [360, 720]
  let width = 0;
  let height = 0;
  try {
    await new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        width = img.naturalWidth;
        height = img.naturalHeight;
        URL.revokeObjectURL(url);
        resolve();
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("无法解码图像尺寸"));
      };
      img.src = url;
    });

    // 步骤一：宽高比 9:16（允许细微裁剪误差）
    const ratio = height / width;
    const idealRatio = 16.0 / 9.0;
    const relError = Math.abs(ratio - idealRatio) / idealRatio;
    const idealH = Math.round(width * 16.0 / 9.0);
    if (relError > 0.025 && Math.abs(height - idealH) > 5) {
      errors.push(`图片宽高比必须为 9:16（当前尺寸为 ${width}×${height}，不符合 9:16 宽高比要求）`);
    }

    // 步骤二：宽度区间 [360, 720]
    if (width < 360 || width > 720) {
      errors.push(`图片宽度必须在 [360, 720] 区间内（当前检测为 ${width}px）`);
    }
  } catch (err) {
    errors.push("解析图片尺寸失败：" + err.message);
  }

  // 2. 格式与扩展名（必须严格为 .jpg，二进制须为标准 JPG）
  const lowerName = file.name.toLowerCase();
  if (!lowerName.endsWith(".jpg")) {
    const ext = lowerName.includes(".") ? lowerName.split(".").pop() : "无";
    errors.push(`扩展名必须是 .jpg（当前为 .${ext}）`);
  }

  // 3. 二进制流检查魔数与导出质量（80%）
  let quality = null;
  try {
    const buffer = await file.arrayBuffer();
    const u8 = new Uint8Array(buffer);
    if (u8.length < 4 || u8[0] !== 0xff || u8[1] !== 0xd8) {
      errors.push("文件不是有效的 JPG 格式图像");
    } else {
      quality = estimateJpegQuality(u8);
      if (quality === null) {
        errors.push("未能检测到 JPG 量化表");
      } else if (quality < 78 || quality > 82) {
        errors.push(`导出质量必须为 80%（当前检测约为 ${quality}%，请在导出时将质量设为 80% 默认值）`);
      }
    }
  } catch (err) {
    errors.push("读取图片二进制失败：" + err.message);
  }

  return {
    ok: errors.length === 0,
    errors,
    info: { width, height, quality: quality ?? 80 },
  };
}

function helpAdminReview() {
  return `
    <details class="help-card help-fold">
      <summary>审核与裁图说明（以 Windows 自带「照片」软件为例）</summary>
      <ul class="help-steps">
        <li>
          <strong>第一步·下载原图与裁剪 9:16 宽高比</strong>
          <div class="help-desc">
            打开原图链接并<strong>下载原图</strong>。Pixiv 多图若链接带 <code>#N</code>（从 1 起），请翻到对应那一张再下。<br />
            用 Windows 自带「照片」打开进入【编辑】，点击下方的【自由】（宽高比选项）切换为【<strong>9:16</strong>】，调整取景后保存。<br />
            <span class="muted">（注：此步骤仅负责裁剪宽高比，请勿在此缩放；宽度留到下一步调整）</span>
          </div>
        </li>
        <li>
          <strong>第二步·调整图片大小（宽度、格式、质量）</strong>
          <div class="help-desc">
            在「照片」右上角菜单（…）中选择【<strong>调整图片大小</strong>】：
            <ul>
              <li><strong>宽度</strong>：输入数值调整到 <strong>[360, 720]</strong> 区间内（必须保持锁定宽高比，高度会自动联动）；</li>
              <li><strong>格式</strong>：统一选择 <strong>.jpg</strong>；</li>
              <li><strong>质量</strong>：统一保持为 <strong>80%</strong>（系统默认值）。</li>
            </ul>
          </div>
        </li>
        <li>
          <strong>四维自动检测机制</strong>
          <div class="help-desc">
            选择文件与上传时，系统会自动严格检测上述 4 项规范：<br />
            <code>宽高比 9:16（允许细微裁剪误差）</code> · <code>宽度 [360, 720]</code> · <code>格式 .jpg</code> · <code>导出质量 80%</code><br />
            若有任何一项不达标，系统将直接拦截并提示原因，无法上传。
          </div>
        </li>
        <li>
          <strong>通过并上传</strong>
          <div class="help-desc">
            上传裁好的 .jpg 本图，图号默认顺延。<br />
            <strong>注意</strong>：审核通过仅写入网页图库，<strong>必须在 Discord 执行 <code>更新图集</code> 指令后</strong>，机器人本地才会同步并支持出图。
          </div>
        </li>
        <li>
          <strong>驳回</strong>
          <div class="help-desc">
            勾选原因标签，可再填补充说明。<br />
            提交驳回后，<strong>Bot 会私信通知投稿者</strong>，投稿者也可在「我的投稿」中查看状态。
          </div>
        </li>
      </ul>
    </details>`;
}

async function renderHome() {
  appEl.innerHTML = `<p class="muted">加载角色列表…</p>`;
  try {
    const data = await api("/chars");
    let intro = "";
    if (!currentUser) intro = helpGuest();
    else if (!currentUser.can_submit) intro = helpUnbound();

    if (!data.chars.length) {
      appEl.innerHTML = `${intro}<div class="empty"><p>还没有已发布的图。</p></div>`;
      return;
    }
    const tiles = data.chars
      .map(
        (c, i) => `
      <a class="char-tile" href="${appHref(`char/${c.char_id}`)}" data-link style="animation-delay:${i * 0.03}s">
        ${
          c.cover_url
            ? `<img src="${absUrl(c.cover_url)}" alt="${escapeHtml(c.label)}" loading="lazy" />`
            : `<div class="placeholder">暂无封面</div>`
        }
        <div class="meta">
          <div class="name">${escapeHtml(c.label)}</div>
          <div class="count">${c.image_count} 张 · id ${escapeHtml(c.char_id)}${c.cover_is_official ? " · 官方封面" : ""}</div>
        </div>
      </a>`
      )
      .join("");
    appEl.innerHTML = `
      ${intro}
      <div class="section-head">
        <h1>角色</h1>
        <span class="muted">${data.chars.length} 个</span>
      </div>
      <div class="char-grid">${tiles}</div>`;
  } catch (e) {
    appEl.innerHTML = `<div class="empty">加载失败：${escapeHtml(e.message)}</div>`;
  }
}

async function renderChar(charId) {
  appEl.innerHTML = `<p class="muted">加载图墙…</p>`;
  try {
    const [detail, wall] = await Promise.all([
      api(`/chars/${charId}`),
      api(`/chars/${charId}/images`),
    ]);
    if (!wall.images.length) {
      appEl.innerHTML = `
        <div class="section-head">
          <a class="crumb" href="${appHref()}" data-link>← 角色列表</a>
          <h1>${escapeHtml(detail.label)}</h1>
        </div>
        <div class="empty">还没有用户上传的面板图。</div>`;
      return;
    }
    const gallery = wall.images.map((im) => ({
      image_id: im.image_id,
      pile_url: im.pile_url,
      orig_url: im.orig_url || "",
      submitter: im.submitter || "",
      reviewer: im.reviewer || "",
      label: detail.label,
    }));
    const items = gallery
      .map(
        (im, i) => `
      <button type="button" class="wall-item" style="animation-delay:${i * 0.03}s" data-index="${i}">
        <img src="${absUrl(im.pile_url)}" alt="#${im.image_id}" loading="lazy" />
      </button>`
      )
      .join("");
    appEl.innerHTML = `
      <div class="section-head">
        <a class="crumb" href="${appHref()}" data-link>← 角色列表</a>
        <h1>${escapeHtml(detail.label)}</h1>
        <span class="muted">id ${escapeHtml(detail.char_id)} · ${wall.images.length} 张</span>
      </div>
      <div class="wall">${items}</div>
      <div id="lightbox-root"></div>`;
    appEl.querySelectorAll(".wall-item").forEach((btn) => {
      btn.addEventListener("click", () => openLightbox(gallery, Number(btn.dataset.index)));
    });
  } catch (e) {
    appEl.innerHTML = `<div class="empty">加载失败：${escapeHtml(e.message)}</div>`;
  }
}

async function renderSubmit() {
  const loginHref = `${publicPrefix}/auth/login`;
  if (!currentUser) {
    appEl.innerHTML = `${helpGuest()}<p class="muted"><a href="${loginHref}">Discord 登录</a> 后再投稿。</p>`;
    return;
  }
  if (!currentUser.can_submit) {
    appEl.innerHTML = helpUnbound();
    return;
  }
  appEl.innerHTML = `<p class="muted">加载角色…</p>`;
  try {
    const data = await api("/chars");
    const opts = data.chars
      .map((c) => `<option value="${escapeHtml(c.char_id)}">${escapeHtml(c.label)}（${escapeHtml(c.char_id)}）</option>`)
      .join("");
    appEl.innerHTML = `
      ${helpSubmitter()}
      <div class="section-head"><h1>投稿</h1></div>
      <form class="form-card" id="submit-form">
        <label>角色
          <input list="char-list" name="char_label" id="char-input" placeholder="输入名称或 id 筛选" autocomplete="off" />
          <select name="char_id" id="char-select" required>
            <option value="">选择角色</option>
            ${opts}
          </select>
        </label>
        <datalist id="char-list">
          ${data.chars.map((c) => `<option value="${escapeHtml(c.label)}"></option>`).join("")}
        </datalist>
        <label>原图链接
          <input type="url" name="orig_url" required placeholder="https://www.pixiv.net/artworks/… 或其它原图页" />
        </label>
        <p class="field-hint">只交链接即可；裁剪由管理员完成。</p>
        <button type="submit" class="btn">提交审核</button>
        <p class="form-msg muted" id="submit-msg"></p>
      </form>`;

    const select = document.getElementById("char-select");
    const input = document.getElementById("char-input");
    input.addEventListener("change", () => {
      const v = input.value.trim();
      const hit = data.chars.find((c) => c.label === v || c.char_id === v || c.name === v);
      if (hit) select.value = hit.char_id;
    });

    document.getElementById("submit-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("submit-msg");
      const charId = select.value;
      const origUrl = e.target.orig_url.value.trim();
      msg.textContent = "提交中…";
      try {
        await api("/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ char_id: charId, orig_url: origUrl }),
        });
        msg.textContent = "已提交，等待审核。可在「我的投稿」查看状态。";
        e.target.reset();
      } catch (err) {
        msg.textContent = err.message || String(err);
      }
    });
  } catch (e) {
    appEl.innerHTML = `<div class="empty">加载失败：${escapeHtml(e.message)}</div>`;
  }
}

function statusLabel(s) {
  if (s === "pending") return "待审";
  if (s === "approved") return "已通过";
  if (s === "rejected") return "已驳回";
  return s;
}

async function renderMySubmissions() {
  const loginHref = `${publicPrefix}/auth/login`;
  if (!currentUser) {
    appEl.innerHTML = `<div class="help-card"><p>请先 <a href="${loginHref}">Discord 登录</a> 查看投稿。</p></div>`;
    return;
  }
  appEl.innerHTML = `<p class="muted">加载中…</p>`;
  try {
    const data = await api("/me/submissions");
    if (!data.submissions.length) {
      appEl.innerHTML = `
        <div class="section-head"><h1>我的投稿</h1></div>
        <div class="empty">还没有投稿。<a href="${appHref("submit")}" data-link>去投稿</a></div>`;
      return;
    }
    const rows = data.submissions
      .map((s) => {
        const tags = (s.reject_tags || []).join("、");
        const note = s.reject_note ? escapeHtml(s.reject_note) : "";
        const extra =
          s.status === "rejected"
            ? `<div class="sub-extra">原因：${escapeHtml(tags || "—")}${
                note ? `<br />说明：${note}` : ""
              }</div>`
            : s.status === "approved"
              ? `<div class="sub-extra">图号：${escapeHtml(s.image_id || "")}<br />指令：${escapeHtml(
                  `${s.char_name || s.char_id}面板${s.image_id || ""}`
                )}</div>`
              : "";
        return `
          <article class="sub-card status-${escapeHtml(s.status)}">
            <div class="sub-top">
              <strong>${escapeHtml(s.char_name || s.char_id)}</strong>
              <span class="badge">${statusLabel(s.status)}</span>
            </div>
            <div class="muted"><a href="${escapeHtml(s.orig_url)}" target="_blank" rel="noopener">原图链接</a> · ${escapeHtml(formatLocalTime(s.created_at))}</div>
            ${extra}
          </article>`;
      })
      .join("");
    appEl.innerHTML = `
      <div class="section-head"><h1>我的投稿</h1><span class="muted">${data.submissions.length}</span></div>
      <div class="sub-list">${rows}</div>`;
  } catch (e) {
    appEl.innerHTML = `<div class="empty">加载失败：${escapeHtml(e.message)}</div>`;
  }
}

async function renderReviewHistory() {
  if (!currentUser?.is_admin) {
    appEl.innerHTML = `<div class="empty">需要管理员权限。</div>`;
    return;
  }
  const pageSize = 10;
  const rawPage = Number(new URLSearchParams(location.search).get("page") || "1");
  const page = Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : 1;
  appEl.innerHTML = `<p class="muted">加载审核历史…</p>`;
  try {
    const data = await api(`/admin/history?page=${page}&page_size=${pageSize}`);
    const items = data.submissions || [];
    const total = data.total ?? items.length;
    const pages = data.pages || 1;
    const cur = data.page || page;
    if (!total) {
      appEl.innerHTML = `
        <div class="section-head"><h1>审核历史</h1></div>
        <div class="empty">还没有已处理的投稿。</div>`;
      return;
    }
    const rows = items
      .map((s) => {
        const tags = (s.reject_tags || []).join("、");
        const note = s.reject_note ? escapeHtml(s.reject_note) : "";
        const reviewer = escapeHtml(s.reviewer_name || s.reviewer_id || "—");
        const submitter = escapeHtml(s.submitter_name || s.submitter_id || "—");
        const reviewed = escapeHtml(formatLocalTime(s.reviewed_at || s.created_at));
        let extra = "";
        if (s.status === "rejected") {
          extra = `<div class="sub-extra">原因：${escapeHtml(tags || "—")}${
            note ? `<br />说明：${note}` : ""
          }</div>`;
        } else if (s.status === "approved") {
          extra = `<div class="sub-extra">图号：${escapeHtml(s.image_id || "")}<br />指令：${escapeHtml(
            `${s.char_name || s.char_id}面板${s.image_id || ""}`
          )}</div>`;
        }
        return `
          <article class="sub-card status-${escapeHtml(s.status)}">
            <div class="sub-top">
              <strong>${escapeHtml(s.char_name || s.char_id)}</strong>
              <span class="badge">${statusLabel(s.status)}</span>
            </div>
            <div class="muted">投稿人 ${submitter} · 审核人 ${reviewer} · ${reviewed}</div>
            <div class="muted"><a href="${escapeHtml(s.orig_url)}" target="_blank" rel="noopener">原图链接</a></div>
            ${extra}
          </article>`;
      })
      .join("");
    const prevDisabled = cur <= 1 ? "disabled" : "";
    const nextDisabled = cur >= pages ? "disabled" : "";
    const prevHref = appHref(`history?page=${cur - 1}`);
    const nextHref = appHref(`history?page=${cur + 1}`);
    const pager =
      pages > 1
        ? `<nav class="pager" aria-label="审核历史分页">
            <a class="btn ghost" href="${prevHref}" data-link ${prevDisabled}>上一页</a>
            <span class="muted">第 ${cur} / ${pages} 页</span>
            <a class="btn ghost" href="${nextHref}" data-link ${nextDisabled}>下一页</a>
          </nav>`
        : "";
    appEl.innerHTML = `
      <div class="section-head"><h1>审核历史</h1><span class="muted">${total} 条 · 每页 ${pageSize}</span></div>
      <p class="muted tiny-hint" style="margin-top:0">全体管理员与主人的通过 / 驳回记录（新→旧）。</p>
      <div class="sub-list">${rows}</div>
      ${pager}`;
  } catch (e) {
    appEl.innerHTML = `<div class="empty">加载失败：${escapeHtml(e.message)}</div>`;
  }
}

async function renderReview() {
  if (!currentUser?.is_admin) {
    appEl.innerHTML = `<div class="empty">需要管理员权限。</div>`;
    return;
  }
  appEl.innerHTML = `<p class="muted">加载待审…</p>`;
  try {
    const data = await api("/admin/pending");
    const tags = data.reject_tags || [];
    if (!data.submissions.length) {
      appEl.innerHTML = `${helpAdminReview()}<div class="section-head"><h1>审核</h1></div><div class="empty">暂无待审投稿。</div>`;
      return;
    }
    const cards = data.submissions
      .map((s) => {
        const tagChecks = tags
          .map(
            (t) =>
              `<label class="tag-check"><input type="checkbox" value="${escapeHtml(t)}" /> ${escapeHtml(t)}</label>`
          )
          .join("");
        return `
          <details class="review-card review-fold" data-id="${escapeHtml(s.id)}">
            <summary class="review-summary">
              <span class="review-summary-main">
                <strong>${escapeHtml(s.char_name || s.char_id)}</strong>
                <span class="muted">${escapeHtml(s.submitter_name || s.submitter_id)}</span>
              </span>
              <span class="muted review-summary-time">${escapeHtml(formatLocalTime(s.created_at))}</span>
            </summary>
            <div class="review-body">
              <p><a href="${escapeHtml(s.orig_url)}" target="_blank" rel="noopener">打开原图链接</a></p>
              <div class="review-branches">
                <div class="review-approve">
                  <p class="review-branch-title">通过</p>
                  <label>本图（裁好的 JPG）<input type="file" accept=".jpg,image/jpeg" data-pile /></label>
                  <label>图号（推荐留空=自动顺延）
                    <input type="text" maxlength="4" placeholder="例如 0009" data-iid />
                  </label>
                  <p class="muted tiny-hint">${
                    currentUser?.is_master
                      ? "留空将自动分配下一个空号（推荐）。填已有图号会<strong>覆盖</strong>该号本图与原图链接（仅主人可覆盖）。"
                      : "留空将自动分配下一个空号（推荐）。填已有图号会被拒绝；覆盖已有图仅主人可操作。"
                  }</p>
                  <div class="file-check-result" data-file-status></div>
                  <button type="button" class="btn" data-approve>通过并上传</button>
                </div>
                <div class="review-reject">
                  <p class="review-branch-title">驳回</p>
                  <div class="tag-grid">${tagChecks}</div>
                  <label>补充说明<textarea rows="2" data-note placeholder="可选"></textarea></label>
                  <button type="button" class="btn ghost" data-reject>驳回</button>
                </div>
              </div>
              <p class="form-msg muted" data-msg></p>
            </div>
          </details>`;
      })
      .join("");
    appEl.innerHTML = `
      ${helpAdminReview()}
      <div class="section-head"><h1>审核</h1><span class="muted">${data.submissions.length} 待审</span></div>
      <div class="review-list">${cards}</div>`;

    appEl.querySelectorAll(".review-card").forEach((card) => {
      const id = card.dataset.id;
      const msg = card.querySelector("[data-msg]");
      const fileInput = card.querySelector("[data-pile]");
      const approveBtn = card.querySelector("[data-approve]");
      const statusBox = card.querySelector("[data-file-status]");

      fileInput.addEventListener("change", async () => {
        const file = fileInput.files?.[0];
        msg.textContent = "";
        if (!file) {
          statusBox.className = "file-check-result";
          statusBox.textContent = "";
          approveBtn.disabled = false;
          return;
        }
        statusBox.className = "file-check-result";
        statusBox.textContent = "检测图片规范中…";
        const check = await validatePileFile(file);
        if (!check.ok) {
          statusBox.className = "file-check-result error";
          statusBox.innerHTML = `<strong>❌ 图片不符合规范，无法上传：</strong><ul>${check.errors
            .map((e) => `<li>${escapeHtml(e)}</li>`)
            .join("")}</ul>`;
          approveBtn.disabled = true;
        } else {
          statusBox.className = "file-check-result success";
          statusBox.textContent = `✅ 检测通过：宽高比 9:16（${check.info.width}×${check.info.height}） · 宽度在 [360, 720] · 格式 .jpg · 导出质量 ${check.info.quality}%`;
          approveBtn.disabled = false;
        }
      });

      approveBtn.addEventListener("click", async () => {
        const file = fileInput.files?.[0];
        if (!file) {
          msg.textContent = "请先选择裁剪后的本图文件";
          return;
        }
        const check = await validatePileFile(file);
        if (!check.ok) {
          statusBox.className = "file-check-result error";
          statusBox.innerHTML = `<strong>❌ 图片不符合规范，无法上传：</strong><ul>${check.errors
            .map((e) => `<li>${escapeHtml(e)}</li>`)
            .join("")}</ul>`;
          approveBtn.disabled = true;
          return;
        }
        const iidVal = card.querySelector("[data-iid]").value.trim();
        if (iidVal && currentUser?.is_master) {
          const ok = window.confirm(
            `将写入图号 ${iidVal.padStart(4, "0").slice(-4)}。\n若该号已存在，会覆盖旧本图与原图链接。\n确定继续？`
          );
          if (!ok) return;
        }
        const fd = new FormData();
        fd.append("pile", file);
        fd.append("image_id", iidVal);
        msg.textContent = "上传中…";
        approveBtn.disabled = true;
        try {
          const res = await fetch(`${publicPrefix}/api/admin/submissions/${id}/approve`, {
            method: "POST",
            credentials: "same-origin",
            body: fd,
          });
          const body = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(body.detail || res.statusText);
          const ov = body.submission?.overwritten ? "（已覆盖旧图）" : "";
          msg.textContent =
            "已通过" +
            ov +
            (body.notify_error ? `（私信：${body.notify_error}）` : "（已尝试私信）");
          setTimeout(() => renderReview(), 800);
        } catch (err) {
          msg.textContent = err.message || String(err);
          approveBtn.disabled = false;
        }
      });
      card.querySelector("[data-reject]").addEventListener("click", async () => {
        const selected = [...card.querySelectorAll('.tag-check input:checked')].map((el) => el.value);
        const note = card.querySelector("[data-note]").value;
        if (!selected.length && !note.trim()) {
          msg.textContent = "请至少选一个标签或填写说明";
          return;
        }
        msg.textContent = "提交驳回…";
        try {
          const body = await api(`/admin/submissions/${id}/reject`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tags: selected, note }),
          });
          msg.textContent =
            "已驳回" + (body.notify_error ? `（私信：${body.notify_error}）` : "（已尝试私信）");
          setTimeout(() => renderReview(), 800);
        } catch (err) {
          msg.textContent = err.message || String(err);
        }
      });
    });
  } catch (e) {
    appEl.innerHTML = `<div class="empty">加载失败：${escapeHtml(e.message)}</div>`;
  }
}

function withDownload(url) {
  const u = absUrl(url);
  if (!u) return "#";
  return u.includes("?") ? `${u}&download=1` : `${u}?download=1`;
}

function closeLightbox(immediate = false) {
  if (lightboxKeyHandler) {
    window.removeEventListener("keydown", lightboxKeyHandler);
    lightboxKeyHandler = null;
  }
  lightboxState = null;
  const root = document.getElementById("lightbox-root");
  if (!root) return;
  if (immediate) {
    root.innerHTML = "";
    return;
  }
  const box = root.querySelector(".lightbox");
  if (!box) {
    root.innerHTML = "";
    return;
  }
  box.classList.remove("open");
  setTimeout(() => {
    root.innerHTML = "";
  }, 180);
}

function openLightbox(list, index) {
  lightboxState = { list, index };
  renderLightbox();
}

function stepLightbox(delta) {
  if (!lightboxState) return;
  const next = lightboxState.index + delta;
  if (next < 0 || next >= lightboxState.list.length) return;
  lightboxState.index = next;
  renderLightbox();
}

function renderLightbox() {
  if (!lightboxState) return;
  const { list, index } = lightboxState;
  const data = list[index];
  const root = document.getElementById("lightbox-root");
  if (!root || !data) return;
  const pileSrc = absUrl(data.pile_url);
  const label = escapeHtml(data.label || "");
  const imageId = escapeHtml(data.image_id);
  const atStart = index <= 0;
  const atEnd = index >= list.length - 1;
  const hasOrig = Boolean(data.orig_url);
  const origHref = hasOrig ? escapeHtml(data.orig_url) : "#";
  if (lightboxKeyHandler) window.removeEventListener("keydown", lightboxKeyHandler);
  root.innerHTML = `
    <div class="lightbox open" role="dialog" aria-modal="true">
      <div class="lightbox-wrap">
        <button type="button" class="nav-btn prev" data-prev aria-label="上一张" ${atStart ? "disabled" : ""}>‹</button>
        <button type="button" class="nav-btn next" data-next aria-label="下一张" ${atEnd ? "disabled" : ""}>›</button>
        <button type="button" class="close-x" aria-label="关闭">×</button>
        <div class="lightbox-panel">
          <figure class="lightbox-figure"><img src="${pileSrc}" alt="#${imageId}" /></figure>
          <div class="lightbox-side">
            <h2>${label}</h2>
            <dl>
              <dt>图号</dt><dd>${imageId}</dd>
              <dt>指令</dt><dd>${label}面板${imageId}</dd>
              <dt>投稿人</dt><dd>${escapeHtml(data.submitter || "—")}</dd>
              <dt>审核人</dt><dd>${escapeHtml(data.reviewer || "—")}</dd>
              <dt>序号</dt><dd>${index + 1} / ${list.length}</dd>
            </dl>
            <div class="actions">
              <button type="button" class="btn ghost" data-prev ${atStart ? "disabled" : ""}>上一张</button>
              <button type="button" class="btn ghost" data-next ${atEnd ? "disabled" : ""}>下一张</button>
              <a class="btn" href="${withDownload(data.pile_url)}">下载本图</a>
              ${
                hasOrig
                  ? `<a class="btn" href="${origHref}" target="_blank" rel="noopener noreferrer">原图链接</a>`
                  : `<span class="btn ghost" aria-disabled="true">原图链接</span>`
              }
              <button type="button" class="btn ghost" data-close>关闭</button>
            </div>
          </div>
        </div>
      </div>
    </div>`;
  const box = root.querySelector(".lightbox");
  root.querySelector(".close-x").addEventListener("click", () => closeLightbox());
  root.querySelector("[data-close]").addEventListener("click", () => closeLightbox());
  root.querySelectorAll("[data-prev]").forEach((el) =>
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      stepLightbox(-1);
    })
  );
  root.querySelectorAll("[data-next]").forEach((el) =>
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      stepLightbox(1);
    })
  );
  box.addEventListener("click", (e) => {
    if (e.target === box) closeLightbox();
  });
  lightboxKeyHandler = (e) => {
    if (e.key === "Escape") closeLightbox();
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      stepLightbox(-1);
    }
    if (e.key === "ArrowRight") {
      e.preventDefault();
      stepLightbox(1);
    }
  };
  window.addEventListener("keydown", lightboxKeyHandler);
}

document.addEventListener("click", (e) => {
  const a = e.target.closest("a[data-link]");
  if (!a || a.target === "_blank" || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const url = new URL(a.getAttribute("href") || "", location.href);
  if (url.origin !== location.origin) return;
  if (publicPrefix && !url.pathname.startsWith(publicPrefix)) return;
  e.preventDefault();
  history.pushState(null, "", url.pathname + url.search);
  route();
});

window.addEventListener("popstate", route);
migrateHashRoute();
refreshAuth().then(() => route());
