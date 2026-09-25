"""Connection Pooling Optimization [SEED: 2399].
Wraps httpx to maintain persistent TCP/TLS connections for high concurrency.
"""
import httpx

class GraphQLConnectionPool:
    def __init__(self, max_connections=100, max_keepalive=20):
        self.client = httpx.Client(
            limits=httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_keepalive),
            timeout=30.0
        )
    
    def get(self, url, **kwargs):
        return self.client.get(url, **kwargs)

    def post(self, url, **kwargs):
        return self.client.post(url, **kwargs)
        
    def close(self):
        self.client.close()
