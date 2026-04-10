bind = "unix:/run/gunicorn/nihar-website.sock"
workers = 3
timeout = 300  # pyseobnr waveform generation can take 30-120s
accesslog = "/home/deploy/nihar-website/logs/gunicorn-access.log"
errorlog = "/home/deploy/nihar-website/logs/gunicorn-error.log"
loglevel = "info"
capture_output = True
