FROM python:3.9

RUN pip3 install -U pip setuptools wheel pipenv
RUN useradd -ms /bin/bash -d /mb-exporter -u 8999 -U mb-exporter

WORKDIR /mb-exporter/src
COPY Pipfile* /mb-exporter/src/
RUN pipenv sync --system

COPY . /mb-exporter/src
WORKDIR /mb-exporter

USER mb-exporter
ENV PYTHONUNBUFFERED=1

CMD [ "python", "/mb-exporter/src/main.py" ]
