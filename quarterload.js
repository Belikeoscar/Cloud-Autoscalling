import http from 'k6/http';
import { sleep } from 'k6';
export const options = {
  stages: [
    { duration: '2m', target: 1 },
    { duration: '3m', target: 6 },
    { duration: '2m', target: 3 },
    { duration: '1m', target: 10 },
    { duration: '3m', target: 10 },
    { duration: '3m', target: 1 },
    { duration: '3m', target: 8 },
    { duration: '3m', target: 0 },
  ],
};
export default function () {
  http.get('http://scaling-app/work');
  sleep(0.1);
}
