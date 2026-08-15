import logging, json, sys, time

class JSONFormatter(logging.Formatter):
    def format(self, record):
        out = {
          "ts": int(time.time()*1000), "level": record.levelname,
          "msg": record.getMessage(), "logger": record.name,
        }
        for k in ("request_id", "latency_ms", "top_k", "chunks"):
            if hasattr(record, k): out[k] = getattr(record, k)
        return json.dumps(out)

def init():
    h = logging.StreamHandler(sys.stdout); h.setFormatter(JSONFormatter())
    root = logging.getLogger(); root.handlers = [h]; root.setLevel(logging.INFO)