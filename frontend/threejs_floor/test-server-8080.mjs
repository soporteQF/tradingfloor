import http from 'http';
const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'text/html'});
  res.end('<h1>Test Server Works on 8080!</h1>');
});
server.listen(8080, '127.0.0.1', () => console.log('Server running on http://127.0.0.1:8080'));