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
//    (на боте выставляется WEBHOOK_BASE_URL=https://<worker>.workers.dev
//     и TELEGRAM_WEBHOOK_PATH=/hook/<name>)

const HOOKS = {
  // name → куда пересылать апдейты Telegram
  selfheal: "https://bot.selfheal369.ru/webhooks/telegram",
};

const TG_API = "https://api.telegram.org";

// Каким ботам разрешено ходить через релей (префикс токена = числовой id бота)
const ALLOWED_BOT_IDS = ["8801587624"];

// Origin по умолчанию для /webhooks/* (основной бот)
const DEFAULT_ORIGIN = "https://bot.selfheal369.ru";

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
      return fetch(target + url.search, {
        method: request.method,
        headers: request.headers,
        body: request.body,
      });
    }

    // Входящий вебхук по пути /webhooks/* — пересылаем на origin как есть
    if (path.startsWith("/webhooks/")) {
      return fetch(DEFAULT_ORIGIN + path + url.search, {
        method: request.method,
        headers: request.headers,
        body: request.body,
      });
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
