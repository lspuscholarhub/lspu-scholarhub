web: gunicorn run:app --bind 0.0.0.0:$PORT --workers 3 --threads 8 --worker-tmp-dir /dev/shm --timeout 120 --graceful-timeout 30 --keep-alive 5
