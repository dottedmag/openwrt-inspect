import re, email.parser, io

from . import urlsession, urlcache, ipk

_SRC_RX = re.compile(r'^src/gz \S+ (\S+)$')

def source_list(fh):
    for line in io.TextIOWrapper(fh):
        m = _SRC_RX.match(line)
        if m is not None:
            yield m[1]

def system_sources_list(t):
    sources = set()
    for f in ['./etc/opkg/customfeeds.conf', './etc/opkg/distfeeds.conf']:
        with t.extractfile(f) as fh:
            sources.update(source_list(fh))
    return sources

def _split_para(content):
    for para in content.split(b'\n\n'):
        if para != b'':
            yield para

_parser = email.parser.BytesParser()

def packages(u, content):
    for para in _split_para(content):
        msg = _parser.parsebytes(para)
        url = u+'/'+msg['Filename']
        yield {'package': msg['Package'], 'filename': msg['Filename'],
               'sha256sum': msg['SHA256sum'], 'version': msg['Version'],
               'arch': msg['Architecture'], 'url': url}

# PKG_LIST_OMISSIONS = {
#     'http://downloads.lede-project.org/releases/17.01.4/targets/ar71xx/generic/packages':
#     [
#         {'package': 'libc',
#          'filename': 'libc_1.1.16-1_mips_24kc.ipk',
#          'sha256sum': 'eed92e896e133169d2e64df6af5b598c06474f9cfb7a0bffa323dbd921b27b21',
#          'version': '1.1.16-1',
#          'arch': 'mips_24kc',
#          'url': 'https://archive.openwrt.org/releases/17.01.4/targets/ar71xx/generic/packages/libc_1.1.16-1_mips_24kc.ipk'},
#         {'package': 'kernel',
#          'filename': 'kernel_4.4.92-1-45d282495a15974d60f8edb091d0e2a9_mips_24kc.ipk',
#          'sha256sum': 'ec3a2e25680eaf738ab76aabc63f98ed24e93b03af2d9ee0f57026bd59ec0cae',
#          'version': '4.4.92-1-45d282495a15974d60f8edb091d0e2a9',
#          'arch': 'mips_24kc',
#          'url': 'https://downloads.lede-project.org/releases/17.01.4/targets/ar71xx/generic/packages/kernel_4.4.92-1-45d282495a15974d60f8edb091d0e2a9_mips_24kc.ipk'}
#     ]
# }

def sources_pkg_list(sources):
    pkgs = {}
    for source in sources:
        for p in packages(source, urlsession.get(source+'/Packages').content):
            pkgs[p['package']] = p
        #if source in PKG_LIST_OMISSIONS:
        #    for p in PKG_LIST_OMISSIONS[source]:
        #        pkgs[p['package']] = p
    return pkgs

def installed_packages(fh):
    for para in _split_para(fh.read()):
        msg = _parser.parsebytes(para)
        if 'Status' not in msg or msg['Status'].split(' ')[2] != 'installed':
            print(msg)
            sys.exit(2)
        yield {'package': msg['Package'], 'arch': msg['Architecture'],
               'version': msg['Version'],
               'auto': msg.get('Auto-Installed') == 'yes'}

def system_pkg_list(t):
    pkgs = {}
    with t.extractfile('./usr/lib/opkg/status') as fh:
        for p in installed_packages(fh):
             pkgs[p['package']] = p
    return pkgs

def canonical_name(tarinfo):
    f = tarinfo.name.lstrip('.')
    if tarinfo.isdir():
        f += '/'
    return f

def system_files(t):
    files = set()
    for m in t.getmembers():
        files.add(canonical_name(m))
    return files

def cmpfiles(tara, a, tarb, b):
    if a.type != b.type:
        print("types mismatch {} != {}".format(a.type, b.type))
        return False
    if a.mode != b.mode:
        print("modes mismatch {} != {}".format(a.mode, b.mode))
        return False
    if a.uid != b.uid:
        print("uid mismatch {} != {}".format(a.uid, b.uid))
        return False
    if a.gid != b.gid:
        print("gid mismatch {} != {}".format(a.gid, b.gid))
        return False
    if a.islnk() or a.issym():
        if a.linkname != b.linkname:
            print("linkname mismatch {} != {}".format(a.linkname, b.linkname))
            return False
    if a.isreg():
        ca = tara.extractfile(a).read()
        cb = tarb.extractfile(b).read()
        if ca != cb:
            print("content mismatch")
            return False
    if a.isdev():
        print(a, b)
        os.exit(42)
    return True

def system(t, romt):
    sources = system_sources_list(t)
    available_packages = sources_pkg_list(sources)

    installed_packages = system_pkg_list(t)
    rom_packages = system_pkg_list(romt)

    sf = system_files(t)

    for name, p in installed_packages.items():
        if name in rom_packages and rom_packages[name]['version'] == p['version']:
            tt = romt.getmember('./usr/lib/opkg/info/'+name+'.list')
            ff = romt.extractfile(tt)
            for line in io.TextIOWrapper(ff, 'UTF-8'):
                filename = line.rstrip()
                sf.discard(filename)
                sf.discard(filename+'/')
                romfile = romt.getmember('.'+filename)
                try:
                    tt = t.getmember('.'+filename)
                except KeyError:
                    print("ROM Removed file", name, '.'+filename)
                    continue
                if not cmpfiles(t, tt, romt, romfile):
                    print("ROM Mismatch", name, tt, romfile)
        else:
            if name not in available_packages:
                print('Not available: '+name)
                continue
            ap = available_packages[name]
            if ap['version'] != p['version']:
                print('Version mismatch: '+name+' '+p['version']+' '
                      +ap['version'])
                continue
            i = ipk.open(urlcache.get(ap['url'], ap['sha256sum']))
            for f in i.getmembers():
                n = canonical_name(f)
                sf.discard(n)
                try:
                    tt = t.getmember(f.name)
                except KeyError:
                    print("Removed file", name, f.name)
                    continue
                if not cmpfiles(t, tt, i, f):
                    print("Mismatch", name, tt, f)

    ff = set()
    for f in sf:
        if f.startswith('/etc/rc.d/'):
            continue
        if f.endswith('/'):
            continue
        if f.startswith('/usr/lib/opkg/'):
            continue
        if f in set(['/etc/board.json',
                     '/etc/fw_env.config',
                     '/etc/passwd-',
                     '/etc/shadow-',
                     '/etc/urandom.seed',
                     '/root/.ssh/known_hosts']):
            continue
        ff.add(f)

    print("Files not in packages", sorted(ff))

    new_packages = set(installed_packages.keys()) - set(rom_packages.keys())
    removed_packages = set(rom_packages.keys()) - set(installed_packages.keys())

    print("New packages:")
    for pkg in new_packages:
        if installed_packages[pkg]['auto']:
            print("    AUTO", pkg)
        else:
            print(pkg)

    print("Removed packages", sorted(removed_packages))
