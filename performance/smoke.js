import http from 'k6/http';
import { check, sleep } from 'k6';

const baseUrl = __ENV.TARGET_BASE_URL || 'http://127.0.0.1:8000';

export const options = {
  vus: 2,
  duration: '10s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

export default function () {
  const response = http.get(`${baseUrl}/health`);
  check(response, { 'health status is 200': (r) => r.status === 200 });
  sleep(0.05);
}
