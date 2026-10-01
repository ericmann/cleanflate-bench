Fixtures for the harness tests. `hello.txt` is the plain text; the compressed
variants are generated with Python's `zlib`/`gzip` modules:

    python3 -c "import zlib,gzip; d=open('hello.txt','rb').read(); \
      c=zlib.compressobj(6,zlib.DEFLATED,-15); open('hello.raw','wb').write(c.compress(d)+c.flush()); \
      open('hello.zlib','wb').write(zlib.compress(d,6)); \
      open('hello.gz','wb').write(gzip.compress(d,6,mtime=0))"
