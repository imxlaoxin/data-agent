from contextlib import contextmanager


@contextmanager
def lifespan(url: str):
    print(f'建立链接: {url}')
    yield f'链接: {url}'
    print(f'断开链接: {url}')

with lifespan(url='http://127.0.0.1:8000/') as conn:
    print(f'基于获取的{conn}，下面开始执行业务操作.')
    print(f'...')
