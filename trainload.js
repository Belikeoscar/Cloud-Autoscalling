import http from 'k6/http';
import { sleep } from 'k6';
export const options = {
  stages: [
    { duration: '2m', target: 5 },
    { duration: '3m', target: 25 },
    { duration: '2m', target: 10 },
    { duration: '1m', target: 40 },
    { duration: '3m', target: 40 },
    { duration: '3m', target: 5 },
    { duration: '3m', target: 30 },
    { duration: '3m', target: 0 },
  ],
};
export default function () {
  http.get('http://scaling-app/work');
  sleep(0.1);
}
