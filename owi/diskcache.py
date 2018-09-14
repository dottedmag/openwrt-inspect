import os, os.path

CACHE_DIR = os.environ['HOME']+'/.cache/owi'

os.makedirs(CACHE_DIR, exist_ok=True)

def _fill(f, fill_fn):
    with open(f+'.tmp', 'wb') as fh:
        fh.write(fill_fn())
    os.rename(f+'.tmp', f)
    return open(f, 'rb')

def get(key, fill_fn):
    f = os.path.join(CACHE_DIR, key)
    try:
        return open(f, 'rb')
    except:
        return _fill(f, fill_fn)
