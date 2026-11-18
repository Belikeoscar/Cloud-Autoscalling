import http from 'k6/http';
export const options = {
  stages: [
    { duration: '1m', target: 5 },
    { duration: '4m', target: 30 },
    { duration: '1m', target: 0 },
  ],
};
export default function () {
  http.get('http://scaling-app/work');
}
