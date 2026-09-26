// Cloudflare Worker — двусторонний релей между VPS и Telegram.
// Используется, когда api.telegram.org недоступен/недостижим с сервера.
//
// 1) Исходящие вызовы Bot API:
//    VPS → https://<worker>.workers.dev/bot<TOKEN>/<METHOD> → api.telegram.org
//    (на боте выставляется TELEGRAM_API_BASE=https://<worker>.workers.dev)
//    Также /file/bot<TOKEN>/<path> для скачивания файлов.
//
// 2) Входящий вебхук:
//    Telegram → https://<worker>.workers.dev/hook/<name> → <origin>/webhooks/telegram
//    или → https://<worker>.workers.dev/webhooks/* → DEFAULT_ORIGIN/webhooks/*
//    (на боте выставляется WEBHOOK_BASE_URL=https://<worker>.workers.dev)
//
// Входящая нога Worker→origin иногда виснет (в сети REG.RU периодически
// теряются соединения от edge Cloudflare). Поэтому upstream-запрос идёт с
// таймаутом и одним ретраем на свежем соединении — иначе Telegram ждёт ~40с
// и шлёт повтор, а кнопка у пользователя «зависает».
// X-Upstream-Ms в ответе — время ноги Worker→origin (диагностика).

const HOOKS = {
  // name → куда пересылать апдейты Telegram
  selfheal: "https://bot.selfheal369.ru/webhooks/telegram",
};

const TG_API = "https://api.telegram.org";

// Каким ботам разрешено ходить через релей (префикс токена = числовой id бота)
const ALLOWED_BOT_IDS = ["8801587624"];

// Origin по умолчанию для /webhooks/* (основной бот)
const DEFAULT_ORIGIN = "https://bot.selfheal369.ru";

const UPSTREAM_TIMEOUT_MS = 6000;

async function relayInbound(target, request) {
  const body = await request.arrayBuffer();
  const t0 = Date.now();
  let lastErr;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const resp = await fetch(target, {
        method: request.method,
        headers: request.headers,
        body: body.byteLength ? body : null,
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      });
      const headers = new Headers(resp.headers);
      headers.set("X-Upstream-Ms", String(Date.now() - t0));
      headers.set("X-Upstream-Attempt", String(attempt + 1));
      return new Response(resp.body, { status: resp.status, headers });
    } catch (e) {
      console.log("upstream fetch failed", target, "attempt", attempt + 1, String(e));
      lastErr = e;
    }
  }
  throw lastErr;
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Входящий вебхук от Telegram (адресованный по имени: /hook/<name>)
    if (path.startsWith("/hook/")) {
      const name = path.slice("/hook/".length).replace(/\/.*$/, "");
      const target = HOOKS[name];
      if (!target) {
        return new Response("unknown hook", { status: 404 });
      }
      return relayInbound(target + url.search, request);
    }

    // Входящий вебхук по пути /webhooks/* — пересылаем на origin как есть
    if (path.startsWith("/webhooks/")) {
      return relayInbound(DEFAULT_ORIGIN + path + url.search, request);
    }

    // Исходящие вызовы Bot API и скачивание файлов — только разрешённым ботам
    if (path.startsWith("/bot") || path.startsWith("/file/bot")) {
      const token = path.replace(/^\/file\/bot|^\/bot/, "").split("/")[0];
      const botId = token.split(":")[0];
      if (!ALLOWED_BOT_IDS.includes(botId)) {
        return new Response("forbidden", { status: 403 });
      }
      return fetch(TG_API + path + url.search, {
        method: request.method,
        headers: request.headers,
        body: request.body,
      });
    }

    return new Response("tg-proxy ok", { status: 200 });
  },
};
