const http = require('http');
const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'text/html'});
  res.end('<h1>Test Server Works!</h1>');
});
server.listen(3000, '0.0.0.0', () => console.log('Server running on http://0.0.0.0:3000'));