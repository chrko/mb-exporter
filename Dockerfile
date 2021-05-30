FROM python:3.9-buster

RUN useradd -ms /bin/bash -d /mb-exporter -u 8999 -U mb-exporter

WORKDIR /mb-exporter

COPY requirements.txt /mb-exporter/src/
RUN pip3 install -U pip setuptools wheel && \
    pip3 install --no-cache-dir -r /mb-exporter/src/requirements.txt

COPY . /mb-exporter/src

USER mb-exporter
ENV PYTHONUNBUFFERED=1

CMD [ "python", "/mb-exporter/src/main.py" ]
