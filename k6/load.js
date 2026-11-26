import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8080';
const VUS = parseInt(__ENV.VUS || '50');          // пиковое число пользователей
const PRODUCTS = 200000;
const HOT = 1000;                                 // «популярные» товары

// 409 («нет на складе») — нормальный ответ, а не ошибка сервера
http.setResponseCallback(http.expectedStatuses({ min: 200, max: 299 }, 409));

export const options = {
  stages: [
    { duration: '15s', target: Math.round(VUS / 2) }, // разгон
    { duration: '45s', target: VUS },                 // пик
    { duration: '10s', target: 0 },                   // спад
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],      // ошибок меньше 1%
    http_req_duration: ['p(95)<500'],    // 95% запросов быстрее 500 мс
    // Пороги по типам запросов нужны, чтобы k6 показал время КАЖДОГО типа
    'http_req_duration{name:product}': ['p(95)<10000'],
    'http_req_duration{name:list}': ['p(95)<10000'],
    'http_req_duration{name:top}': ['p(95)<10000'],
    'http_req_duration{name:search}': ['p(95)<10000'],
    'http_req_duration{name:order}': ['p(95)<10000'],
  },
};

function rand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

// Как в жизни: 80% просмотров — на небольшое число популярных товаров
function productId() {
  return Math.random() < 0.8 ? rand(1, HOT) : rand(1, PRODUCTS);
}

export default function () {
  const r = Math.random();
  let res;

  if (r < 0.60) {          // 60% — карточка товара
    res = http.get(`${BASE}/products/${productId()}`, { tags: { name: 'product' } });
  } else if (r < 0.80) {   // 20% — список категории
    res = http.get(`${BASE}/products?category_id=${rand(1, 50)}&limit=20`, { tags: { name: 'list' } });
  } else if (r < 0.90) {   // 10% — топ продаж
    res = http.get(`${BASE}/stats/top-products`, { tags: { name: 'top' } });
  } else if (r < 0.95) {   // 5% — поиск
    const q = Math.random().toString(16).substring(2, 5);
    res = http.get(`${BASE}/products/search?q=${q}`, { tags: { name: 'search' } });
  } else {                 // 5% — заказ
    res = http.post(
      `${BASE}/orders`,
      JSON.stringify({ product_id: productId(), quantity: 1 }),
      { headers: { 'Content-Type': 'application/json' }, tags: { name: 'order' } },
    );
  }

  check(res, { 'ответ получен': (x) => x.status >= 200 && x.status < 500 });
  sleep(0.1);
}
