import hashlib, functools

from . import diskcache, urlsession

def get(url, sha256sum):
    k = url[url.rindex('/')+1:]+':'+sha256sum
    def dl_url(url):
        response = urlsession.get(url)
        assert hashlib.sha256(response.content).hexdigest() == sha256sum
        return response.content
    return diskcache.get(k, functools.partial(dl_url, url))
