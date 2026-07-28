FROM apify/actor-python-playwright:3.12

WORKDIR /usr/src/app

COPY --chown=myuser:myuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=myuser:myuser . ./

CMD ["python", "main.py"]
