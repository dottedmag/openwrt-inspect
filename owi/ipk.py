import gzip, tarfile, io

def open(fh):
    with gzip.GzipFile(fileobj=fh, mode='rb') as zfh:
        zcontents = zfh.read()
    ipkg_tar = tarfile.open(fileobj=io.BytesIO(zcontents))
    data_fh = ipkg_tar.extractfile('./data.tar.gz')
    with gzip.GzipFile(fileobj=data_fh, mode='rb') as zdata_fh:
        zdata = zdata_fh.read()
    return tarfile.open(fileobj=io.BytesIO(zdata))
