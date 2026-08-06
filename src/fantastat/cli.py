import argparse, os, uvicorn
def main():
    p=argparse.ArgumentParser(); p.add_argument("--cache-dir", default="cache"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8000); p.add_argument("--reload", action="store_true"); a=p.parse_args()
    os.environ["FANTASTAT_CACHE_DIR"]=a.cache_dir
    uvicorn.run("fantastat.api:app", host=a.host, port=a.port, reload=a.reload)
