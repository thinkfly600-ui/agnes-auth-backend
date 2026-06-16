#!/bin/bash
gunicorn -w 2 -b 0.0.0.0:10000 wsgi:app --timeout 120
