import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8080';
const VUS = parseInt(__ENV.VUS || '30');

http.setResponseCallback(http.expectedStatuses({ min: 200, max: 299 }, 409));

export const options = {
  stages: [
    { duration: '10s', target: VUS },
    { duration: '30s', target: VUS },
    { duration: '5s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<300'],
  },
};

export default function () {
  const id = Math.floor(Math.random() * 200000) + 1;
  const res = http.post(
    `${BASE}/orders`,
    JSON.stringify({ product_id: id, quantity: 1 }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(res, { 'заказ принят (201/202)': (x) => x.status === 201 || x.status === 202 });
  sleep(0.05);
}
