import os

import redis
from urllib.parse import urlparse
from rq import Worker, Queue, Connection

listen = ['high', 'default', 'low']

# redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

# conn = redis.from_url(redis_url)
# url = urlparse(os.environ.get("REDIS_URL"))
# conn = redis.Redis(host=url.hostname, port=url.port, username=url.username, password=url.password, ssl=True, ssl_cert_reqs=None)
redis.from_url(os.environ.get("REDIS_URL"))

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()